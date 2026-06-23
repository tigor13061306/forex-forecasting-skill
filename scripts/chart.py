#!/usr/bin/env python3
"""Detailed multi-timeframe candlestick chart with bias, moving averages, key
levels, and an optional trade-setup overlay (entry / stop / target).

This is the "analyst" chart. For the shareable social graphic use card.py.

Single timeframe:
  python chart.py --csv d1.csv --symbol EURUSD --timeframe D1 --bias bearish \
      --support 1.1416,1.1357 --resistance 1.1474,1.1565 --out eurusd.png

Multi-timeframe (one panel per timeframe, side by side):
  python chart.py --csv d1.csv,h4.csv,h1.csv --timeframe D1,H4,H1 \
      --symbol EURUSD --bias bearish --out eurusd_mtf.png

Setup overlay:
  python chart.py --csv h1.csv --timeframe H1 --symbol GBPUSD --bias bearish \
      --direction short --entry 1.327 --stop 1.3305 --target 1.3185,1.3163 \
      --out gbpusd_setup.png

Pure matplotlib, no extra dependencies.
"""

import argparse
import csv
import io
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def load_candles(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if text.startswith("{"):
        try:
            text = json.loads(text)["result"]
        except (ValueError, KeyError):
            pass
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            rows.append({"time": r.get("time", ""), "open": float(r["open"]),
                         "high": float(r["high"]), "low": float(r["low"]),
                         "close": float(r["close"])})
        except (KeyError, ValueError):
            continue
    rows.sort(key=lambda x: x["time"])
    return rows


def sma(values, period):
    return [None if i + 1 < period else sum(values[i + 1 - period:i + 1]) / period
            for i in range(len(values))]


def swing_levels(candles, lookback=3, n=3):
    highs, lows = [], []
    for i in range(lookback, len(candles) - lookback):
        w = candles[i - lookback:i + lookback + 1]
        if candles[i]["high"] == max(x["high"] for x in w):
            highs.append(candles[i]["high"])
        if candles[i]["low"] == min(x["low"] for x in w):
            lows.append(candles[i]["low"])

    def dedup(levels):
        out = []
        for lv in reversed(levels):
            if all(abs(lv - x) > abs(lv) * 1e-3 for x in out):
                out.append(lv)
            if len(out) >= n:
                break
        return out
    return dedup(lows), dedup(highs)


BIAS_COLOR = {"bullish": "#1a9850", "bearish": "#d73027", "neutral": "#888888"}
BIAS_LABEL = {"bullish": "BULLISH ▲", "bearish": "BEARISH ▼", "neutral": "NEUTRAL ◆"}


def draw_candles(ax, view):
    up, down = "#26a69a", "#ef5350"
    width = 0.6
    for i, c in enumerate(view):
        color = up if c["close"] >= c["open"] else down
        ax.plot([i, i], [c["low"], c["high"]], color=color, linewidth=0.8, zorder=2)
        lo = min(c["open"], c["close"])
        ax.add_patch(Rectangle((i - width / 2, lo), width, abs(c["close"] - c["open"]) or 1e-9,
                               facecolor=color, edgecolor=color, zorder=3))


def draw_panel(ax, candles, symbol, tf, sup, res, setup):
    closes = [c["close"] for c in candles]
    s20 = sma(closes, 20)
    s50 = sma(closes, 50)
    bars = min(90, len(candles))
    start = len(candles) - bars
    view = candles[start:]
    x = list(range(len(view)))
    draw_candles(ax, view)
    if any(v is not None for v in s20[start:]):
        ax.plot(x, s20[start:], color="#2962ff", linewidth=1.2, label="SMA20", zorder=4)
    if any(v is not None for v in s50[start:]):
        ax.plot(x, s50[start:], color="#ff6d00", linewidth=1.2, label="SMA50", zorder=4)

    lo = min(c["low"] for c in view)
    hi = max(c["high"] for c in view)
    extra = [v for v in ([setup["entry"], setup["stop"]] + setup["targets"]) if v] if setup else []
    ymin = min([lo] + extra)
    ymax = max([hi] + extra)
    pad = (ymax - ymin) * 0.06 or 1e-4
    ymin -= pad
    ymax += pad

    def inr(v):
        return ymin <= v <= ymax

    for lv in res:
        if inr(lv):
            ax.axhline(lv, color="#d73027", linestyle="--", linewidth=1, alpha=0.8, zorder=1)
            ax.text(len(view) - 1, lv, " R %g" % lv, color="#d73027", va="center", fontsize=7)
    for lv in sup:
        if inr(lv):
            ax.axhline(lv, color="#1a9850", linestyle="--", linewidth=1, alpha=0.8, zorder=1)
            ax.text(len(view) - 1, lv, " S %g" % lv, color="#1a9850", va="center", fontsize=7)

    last = view[-1]["close"]
    ax.axhline(last, color="#333", linestyle=":", linewidth=0.9, alpha=0.7, zorder=1)
    ax.text(0, last, "%g " % last, color="#333", va="center", ha="right", fontsize=7, fontweight="bold")

    if setup:
        e, s = setup["entry"], setup["stop"]
        xr = len(view)
        if e and inr(e):
            ax.axhline(e, color="#1565c0", linewidth=1.6, zorder=5)
            ax.text(xr - 1, e, " Entry %g" % e, color="#1565c0", va="center", fontsize=7, fontweight="bold")
        if e and s and inr(s):
            ax.add_patch(Rectangle((0, min(e, s)), xr, abs(e - s), facecolor="#d73027", alpha=0.10, zorder=0))
            ax.axhline(s, color="#d73027", linewidth=1.4, zorder=5)
            ax.text(xr - 1, s, " Stop %g" % s, color="#d73027", va="center", fontsize=7, fontweight="bold")
        for t in setup["targets"]:
            if t and e and inr(t):
                ax.add_patch(Rectangle((0, min(e, t)), xr, abs(e - t), facecolor="#1a9850", alpha=0.08, zorder=0))
                ax.axhline(t, color="#1a9850", linewidth=1.2, zorder=5)
                ax.text(xr - 1, t, " TP %g" % t, color="#1a9850", va="center", fontsize=7, fontweight="bold")

    ax.set_ylim(ymin, ymax)
    ax.set_title("%s  %s" % (symbol, tf), fontsize=12, fontweight="bold", loc="left")
    ax.margins(x=0.02)
    ax.grid(True, alpha=0.2)
    ax.legend(loc="upper left", fontsize=7)
    ax.set_xticks([])


def render(args):
    csvs = [c.strip() for c in args.csv.split(",") if c.strip()]
    tfs = [t.strip() for t in args.timeframe.split(",")] if args.timeframe else [""] * len(csvs)
    if len(tfs) < len(csvs):
        tfs += [""] * (len(csvs) - len(tfs))

    setup = None
    if args.entry or args.stop or args.target:
        setup = {"direction": (args.direction or "").lower(),
                 "entry": float(args.entry) if args.entry else None,
                 "stop": float(args.stop) if args.stop else None,
                 "targets": [float(v) for v in args.target.split(",") if v.strip()] if args.target else []}

    n = len(csvs)
    fig, axes = plt.subplots(1, n, figsize=(7 * n if n > 1 else 13, 7), squeeze=False)
    axes = axes[0]
    for ax, path, tf in zip(axes, csvs, tfs):
        candles = load_candles(path)
        if len(candles) < 10:
            raise SystemExit("%s: only %d candles parsed; need >= 10" % (path, len(candles)))
        a_sup, a_res = swing_levels(candles)
        sup = [float(v) for v in args.support.split(",") if v.strip()] if args.support else a_sup
        res = [float(v) for v in args.resistance.split(",") if v.strip()] if args.resistance else a_res
        draw_panel(ax, candles, args.symbol, tf, sup, res, setup)

    bias = (args.bias or "neutral").lower()
    badge = "BIAS: %s" % BIAS_LABEL.get(bias, bias.upper())
    if setup and setup["direction"]:
        badge += "   SETUP: %s" % setup["direction"].upper()
    fig.text(0.995, 0.985, badge, ha="right", va="top", fontsize=13, fontweight="bold",
             color="white", bbox=dict(boxstyle="round,pad=0.4",
                                      facecolor=BIAS_COLOR.get(bias, "#888888"), edgecolor="none"))
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(args.out, dpi=130)
    print("Chart saved: %s  (panels: %s)" % (args.out, ", ".join(tfs)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--symbol", default="")
    p.add_argument("--timeframe", default="")
    p.add_argument("--bias", default="neutral")
    p.add_argument("--support", default="")
    p.add_argument("--resistance", default="")
    p.add_argument("--direction", default="")
    p.add_argument("--entry", default="")
    p.add_argument("--stop", default="")
    p.add_argument("--target", default="")
    p.add_argument("--out", required=True)
    render(p.parse_args())


if __name__ == "__main__":
    main()
