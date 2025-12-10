import time
import logging
import ccxt
import pandas as pd

log = logging.getLogger("mean-reversion")

def load_exchange(exchange_id: str, api_key: str = None, secret: str = None, testnet: bool = False):
    ex_class = getattr(ccxt, exchange_id)
    params = {}
    if exchange_id == "binance" and testnet:
        # Use Binance testnet URLs via CCXT: requires ccxt version supporting testnet param OR manual urls
        params = {"options": {"defaultType": "spot"}, "urls": {"api": {"public": "https://testnet.binance.vision/api", "private": "https://testnet.binance.vision/api"}}}
    ex = ex_class({
        "apiKey": api_key or "",
        "secret": secret or "",
        "enableRateLimit": True,
        **params
    })
    return ex

def candles_to_df(ohlcv):
    # ohlcv expected: list of [ts, open, high, low, close, volume]
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    df.set_index("ts", inplace=True)
    return df

def orderbook_imbalance(book, depth=10):
    bids = book.get("bids", [])[:depth]
    asks = book.get("asks", [])[:depth]
    bid_vol = sum([float(b[1]) for b in bids])
    ask_vol = sum([float(a[1]) for a in asks])
    if bid_vol + ask_vol == 0:
        return 0.0
    return (bid_vol - ask_vol) / (bid_vol + ask_vol)

def safe_sleep(seconds):
    try:
        time.sleep(seconds)
    except KeyboardInterrupt:
        raise