"""
Simple backtester that fetches historical candles and simulates the same entry/exit rules.
This is not a high-fidelity simulator (no slippage/fees modeling), but it helps validate params.
"""
import yaml
import ccxt
import pandas as pd
from indicators import rsi, bollinger_bands, percent_change
from utils import candles_to_df, load_exchange

with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

exchange = load_exchange(cfg.get("exchange", "binance"), testnet=False)
symbol = cfg["symbol"]
timeframe = cfg["timeframe"]
limit = 5000

ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
df = candles_to_df(ohlcv)

capital = 1000.0
position = None
trades = []

for i in range( max(cfg["entry"]["bb_period"], cfg["entry"]["rsi_period"]) + cfg["entry"]["lookback_minutes"], len(df) ):
    df_slice = df.iloc[: i+1]
    close = df_slice["close"]
    # compute features
    change = percent_change(close, cfg["entry"]["lookback_minutes"])
    if change < 0 and -change >= cfg["entry"]["drop_pct"]:
        rsi_val = rsi(close, cfg["entry"]["rsi_period"]).iloc[-1]
        if rsi_val <= cfg["entry"]["rsi_threshold"]:
            _, _, lower = bollinger_bands(close, cfg["entry"]["bb_period"], cfg["entry"]["bb_std"])
            price = close.iloc[-1]
            if price <= lower.iloc[-1]:
                # enter long at next candle open (simple assumption)
                entry_price = df_slice["open"].iloc[-1]  # conservative
                size = cfg["position"]["size_usd"] / entry_price
                position = {"entry_price": entry_price, "size": size, "index": i}
                trades.append({"type": "entry", "price": entry_price, "index": i})
    # check exit if position open
    if position:
        current_price = df_slice["close"].iloc[-1]
        tp = position["entry_price"] * (1 + cfg["exit"]["take_profit_pct"] / 100.0)
        sl = position["entry_price"] * (1 + cfg["exit"]["stop_loss_pct"] / 100.0)
        if current_price >= tp or current_price <= sl:
            trades.append({"type": "exit", "price": current_price, "index": i})
            # apply P&L
            pnl = (current_price - position["entry_price"]) * position["size"]
            capital += pnl
            position = None

# summarize
entries = [t for t in trades if t["type"] == "entry"]
exits = [t for t in trades if t["type"] == "exit"]
print("Simulated trades:", len(entries), "entries,", len(exits), "exits")
print("Final capital:", round(capital, 2))
if trades:
    for t in trades[:20]:
        print(t)