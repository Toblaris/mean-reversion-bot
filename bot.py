import time
import logging
import yaml
import ccxt
from collections import deque

import pandas as pd
from indicators import rsi, bollinger_bands, percent_change
from utils import load_exchange, candles_to_df, orderbook_imbalance, safe_sleep

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mean-reversion-bot")

with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

EXCHANGE_ID = cfg.get("exchange", "binance")
SYMBOL = cfg.get("symbol", "DOG/USDT")
TIMEFRAME = cfg.get("timeframe", "1m")
POLL = cfg["polling"]["candle_seconds"]
PAPER = cfg["mode"].get("paper", True)

# Replace with environment variables or .env in production
API_KEY = None
API_SECRET = None

exchange = load_exchange(EXCHANGE_ID, api_key=API_KEY, secret=API_SECRET, testnet=PAPER)

# keep recent candles locally for indicators
lookback_minutes = cfg["entry"]["lookback_minutes"]
candles_needed = max(cfg["entry"]["bb_period"], cfg["entry"]["rsi_period"], lookback_minutes) + 5
prices = deque(maxlen=candles_needed)

open_positions = []  # store dict with entry_price, size, symbol

def fetch_latest_candles(symbol, timeframe, limit):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    return ohlcv

def can_enter(df):
    # requirements:
    # 1) price drop > drop_pct over lookback_minutes
    # 2) RSI(period) < rsi_threshold
    # 3) price touches lower BB
    # 4) orderbook imbalance positive
    close = df["close"]
    drop_pct = cfg["entry"]["drop_pct"]
    lookback = cfg["entry"]["lookback_minutes"]
    change = percent_change(close, lookback)
    if change * -1 < drop_pct and change > 0:
        # not a drop
        return False, {"reason": "not_drop", "change": change}
    # change is negative when drop, percent_change returns current - past / past *100.
    # So convert:
    drop_actual = -change
    rsi_period = cfg["entry"]["rsi_period"]
    rsi_val = rsi(close, rsi_period).iloc[-1]
    if rsi_val > cfg["entry"]["rsi_threshold"]:
        return False, {"reason": "rsi_not_low", "rsi": rsi_val}
    _, upper, lower = bollinger_bands(close, cfg["entry"]["bb_period"], cfg["entry"]["bb_std"])
    price = close.iloc[-1]
    bb_lower = lower.iloc[-1]
    if price > bb_lower * 1.0005:  # allow small epsilon
        return False, {"reason": "not_touching_bb", "price": price, "bb_lower": bb_lower}
    # orderbook imbalance
    book = exchange.fetch_order_book(SYMBOL, limit=20)
    imb = orderbook_imbalance(book, depth=10)
    if imb < cfg["entry"]["ob_imbalance_threshold"]:
        return False, {"reason": "imbalance_low", "imbalance": imb}
    # passed
    return True, {"drop_pct": drop_actual, "rsi": rsi_val, "imbalance": imb, "price": price, "bb_lower": bb_lower}

def size_for_order(price):
    usd = cfg["position"]["size_usd"]
    size = usd / price
    # round depending on asset precision — naive rounding
    return float(round(size, 6))

def place_market_buy(symbol, amount):
    if PAPER:
        log.info("PAPER mode: simulated buy %s %s", amount, symbol)
        return {"id": "paper-" + str(time.time()), "price": None}
    try:
        order = exchange.create_market_buy_order(symbol, amount)
        log.info("Placed market buy: %s", order)
        return order
    except Exception as e:
        log.error("Failed to place buy: %s", e)
        return None

def place_market_sell(symbol, amount):
    if PAPER:
        log.info("PAPER mode: simulated sell %s %s", amount, symbol)
        return {"id": "paper-sell-" + str(time.time()), "price": None}
    try:
        order = exchange.create_market_sell_order(symbol, amount)
        log.info("Placed market sell: %s", order)
        return order
    except Exception as e:
        log.error("Failed to place sell: %s", e)
        return None

def main_loop():
    log.info("Starting main loop for %s on %s (paper=%s)", SYMBOL, EXCHANGE_ID, PAPER)
    while True:
        try:
            ohlcv = fetch_latest_candles(SYMBOL, TIMEFRAME, candles_needed)
            if not ohlcv:
                log.warning("No candles returned")
                safe_sleep(POLL)
                continue
            df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            df.set_index("ts", inplace=True)
            can, meta = can_enter(df)
            log.debug("Can enter: %s meta=%s", can, meta)
            if can and len(open_positions) < cfg["position"]["max_concurrent_positions"]:
                price = df["close"].iloc[-1]
                size = size_for_order(price)
                order = place_market_buy(SYMBOL, size)
                if order:
                    open_positions.append({"entry_price": price, "size": size, "order": order})
                    log.info("Opened position at %.6f size=%s", price, size)
            # manage open positions
            if open_positions:
                last_price = df["close"].iloc[-1]
                to_close = []
                for pos in open_positions:
                    entry = pos["entry_price"]
                    tp = entry * (1 + cfg["exit"]["take_profit_pct"] / 100.0)
                    sl = entry * (1 + cfg["exit"]["stop_loss_pct"] / 100.0)
                    if last_price >= tp:
                        log.info("Take profit reached. entry=%.6f price=%.6f tp=%.6f", entry, last_price, tp)
                        place_market_sell(SYMBOL, pos["size"])
                        to_close.append(pos)
                    elif last_price <= sl:
                        log.info("Stop loss reached. entry=%.6f price=%.6f sl=%.6f", entry, last_price, sl)
                        place_market_sell(SYMBOL, pos["size"])
                        to_close.append(pos)
                for p in to_close:
                    open_positions.remove(p)
            safe_sleep(POLL)
        except KeyboardInterrupt:
            log.info("Interrupted by user")
            break
        except ccxt.NetworkError as e:
            log.error("Network error: %s", e)
            safe_sleep(5)
        except Exception as e:
            log.exception("Unexpected error: %s", e)
            safe_sleep(5)

if __name__ == "__main__":
    main_loop()