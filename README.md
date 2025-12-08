```markdown
# Mean Reversion Altcoin Bot (starter)

What this repo contains
- A configurable, minimal mean-reversion bot implemented in Python using CCXT.
- indicators.py: RSI and Bollinger helpers.
- bot.py: Live/paper trading loop (polling).
- backtest.py: Simple candle-based backtest to validate parameters quickly.
- config.yaml: Example strategy and exchange settings.
- requirements.txt

Strategy summary
- Entry:
  - Price drops > 3.5% over the last 5 minutes
  - RSI(5) < 20
  - Price <= lower Bollinger Band (20, 2)
  - Order-book imbalance (bid_vol - ask_vol)/(bid_vol + ask_vol) > threshold (buyers present)
- Exit:
  - Take profit when price retraces 1.0–1.5% (configurable)
  - Stop loss configurable (e.g., -2%)
- Position sizing: fixed USD (or quote asset) amount in config. Use testnet / paper trading first.

Important warnings
- This is educational code, not financial advice. Test thoroughly on historical data and on testnet or paper trading before trading real funds.
- Watch for slippage, fees, rate limits, API keys and permissions, exchange idiosyncrasies, and latency.
- Consider adding order retry/backoff, concurrency protections, logging and alerting.

Quick start
1. Create a Python virtualenv
2. pip install -r requirements.txt
3. Edit config.yaml (use testnet API keys)
4. Run `python backtest.py` to test parameters
5. When satisfied, run `python bot.py` in paper mode

```
