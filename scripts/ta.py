#!/usr/bin/env python3
"""Technical-analysis helper for the forex-forecasting skill.

Two modes:

1. Indicators from a candle CSV (the MetaTrader get_candles_latest output):
     python ta.py --csv d1.csv --symbol EURUSD --timeframe D1
   Accepts either a raw CSV file or the JSON {"result": "<csv>"} the MCP returns.
   Computes SMA(20/50/200), EMA(20/50), RSI(14), MACD(12/26/9), ATR(14),
   recent swing highs/lows (support/resistance), and a trend label. Prints JSON.

2. Position sizing:
     python ta.py --position-size --balance 99980 --risk-pct 1 \
         --entry 1.1430 --stop 1.1380 --symbol EURUSD
   Returns risk amount, stop distance, and a lot-size estimate.

No third-party dependencies — pure standard library so it runs anywhere.
"""

import argparse
import csv
import io
import json
import sys


# ---------- data loading ----------

def load_candles(path):
    """Load candles from a raw CSV file or a JSON {'result': csv} wrapper.

    Returns a list of dicts with float OHLC, oldest-first.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    # The MCP sometimes wraps the CSV in JSON: {"result": "...csv..."}
    if text.startswith("{"):
        try:
            text = json.loads(text)["result"]
        except (ValueError, KeyError):
            pass

    rows = []
    reader = csv.DictReader(io.StringIO(text))
    for r in reader:
        try:
            rows.append({
                "time": r.get("time", ""),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
            })
        except (KeyError, ValueError):
            continue

    # MCP returns newest-first (index column descending). Sort oldest-first by time.
    rows.sort(key=lambda x: x["time"])
    return rows


# ---------- indicators ----------

def sma(values, period):
    if len(values) < period:
        return None
    return round(sum(values[-period:]) / period, 6)


def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return round(e, 6)


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0))
        losses.append(max(-ch, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _ema_series(values, period):
    k = 2 / (period + 1)
    out = []
    e = None
    for i, v in enumerate(values):
        if i < period - 1:
            out.append(None)
            continue
        if e is None:
            e = sum(values[:period]) / period
        else:
            e = v * k + e * (1 - k)
        out.append(e)
    return out


def macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return None
    ef = _ema_series(closes, fast)
    es = _ema_series(closes, slow)
    macd_line = [
        (a - b) if (a is not None and b is not None) else None
        for a, b in zip(ef, es)
    ]
    valid = [m for m in macd_line if m is not None]
    sig = _ema_series(valid, signal)
    macd_val = round(valid[-1], 6)
    signal_val = round(sig[-1], 6) if sig and sig[-1] is not None else None
    hist = round(macd_val - signal_val, 6) if signal_val is not None else None
    return {"macd": macd_val, "signal": signal_val, "histogram": hist}


def atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h, l = candles[i]["high"], candles[i]["low"]
        pc = candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(trs[:period]) / period
    for tr in trs[period:]:
        a = (a * (period - 1) + tr) / period
    return round(a, 6)


def swing_levels(candles, lookback=3, max_levels=4):
    """Fractal-style swing highs/lows: a high higher than `lookback` bars on
    each side (and the inverse for lows). Returns the most recent unique levels.
    """
    highs, lows = [], []
    n = len(candles)
    for i in range(lookback, n - lookback):
        window = candles[i - lookback:i + lookback + 1]
        c = candles[i]
        if c["high"] == max(w["high"] for w in window):
            highs.append(round(c["high"], 6))
        if c["low"] == min(w["low"] for w in window):
            lows.append(round(c["low"], 6))

    def dedup(levels):
        out = []
        for lv in reversed(levels):  # most recent first
            if all(abs(lv - x) > (abs(lv) * 1e-4 + 1e-9) for x in out):
                out.append(lv)
            if len(out) >= max_levels:
                break
        return out

    return {"resistance": dedup(highs), "support": dedup(lows)}


def trend_label(closes, ma50, ma200):
    last = closes[-1]
    if ma50 is None or ma200 is None:
        if last > closes[0]:
            return "uptrend (insufficient data for MAs)"
        return "downtrend (insufficient data for MAs)"
    if last > ma50 > ma200:
        return "strong uptrend (price > SMA50 > SMA200)"
    if last < ma50 < ma200:
        return "strong downtrend (price < SMA50 < SMA200)"
    if last > ma200:
        return "uptrend / pullback (price above SMA200, mixed shorter MAs)"
    return "downtrend / bounce (price below SMA200, mixed shorter MAs)"


def analyze(path, symbol, timeframe):
    candles = load_candles(path)
    if len(candles) < 30:
        return {"error": f"only {len(candles)} candles parsed; need >= 30"}
    closes = [c["close"] for c in candles]
    ma50 = sma(closes, 50)
    ma200 = sma(closes, 200)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": len(candles),
        "last_close": round(closes[-1], 6),
        "sma": {"20": sma(closes, 20), "50": ma50, "200": ma200},
        "ema": {"20": ema(closes, 20), "50": ema(closes, 50)},
        "rsi14": rsi(closes),
        "macd": macd(closes),
        "atr14": atr(candles),
        "levels": swing_levels(candles),
        "trend": trend_label(closes, ma50, ma200),
    }


# ---------- position sizing ----------

def pip_size(symbol):
    s = symbol.upper()
    if s.endswith("JPY"):
        return 0.01
    if s.startswith("XAU"):  # gold quoted to 0.01
        return 0.01
    if s.startswith("XAG"):  # silver
        return 0.001
    return 0.0001


def position_size(balance, risk_pct, entry, stop, symbol):
    risk_amount = balance * (risk_pct / 100.0)
    pip = pip_size(symbol)
    stop_distance = abs(entry - stop)
    stop_pips = stop_distance / pip if pip else 0
    # Standard FX: pip value per standard lot (100k units) is ~$10 for USD-quoted
    # pairs. Metals differ; this is an approximation the user should confirm with
    # their broker's contract spec.
    pip_value_per_lot = 10.0
    if symbol.upper().startswith("XAU"):
        pip_value_per_lot = 1.0   # 100oz contract, $0.01 move = ~$1
    elif symbol.upper().startswith("XAG"):
        pip_value_per_lot = 5.0
    lots = (risk_amount / (stop_pips * pip_value_per_lot)) if stop_pips else 0
    return {
        "balance": balance,
        "risk_pct": risk_pct,
        "risk_amount": round(risk_amount, 2),
        "entry": entry,
        "stop": stop,
        "stop_distance": round(stop_distance, 6),
        "stop_pips": round(stop_pips, 1),
        "suggested_lots": round(lots, 2),
        "note": "Approximate. Confirm pip value / contract size with your broker.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv")
    p.add_argument("--symbol", default="")
    p.add_argument("--timeframe", default="")
    p.add_argument("--position-size", action="store_true")
    p.add_argument("--balance", type=float)
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--entry", type=float)
    p.add_argument("--stop", type=float)
    args = p.parse_args()

    if args.position_size:
        if None in (args.balance, args.entry, args.stop):
            sys.exit("position sizing needs --balance, --entry, --stop")
        print(json.dumps(position_size(args.balance, args.risk_pct,
                                       args.entry, args.stop, args.symbol),
                         indent=2))
        return

    if not args.csv:
        sys.exit("provide --csv <file> or --position-size")
    print(json.dumps(analyze(args.csv, args.symbol, args.timeframe), indent=2))


if __name__ == "__main__":
    main()
