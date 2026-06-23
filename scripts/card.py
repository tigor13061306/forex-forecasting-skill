#!/usr/bin/env python3
"""Render an attractive, shareable BIAS CARD for social media.

A polished dark-theme square graphic (1080x1080 by default) with a styled
candlestick chart, a bold bias badge, key levels, conviction, and the current
price — designed to be copied and posted. Built on matplotlib (no extra deps).

Example:
  python card.py --csv h1.csv --symbol EURUSD --timeframe H1 \
      --bias bearish --conviction Medium \
      --support 1.1416,1.1357 --resistance 1.1474,1.1565 \
      --price 1.1428 --handle "@yourhandle" --out eurusd_card.png

Optional setup overlay (entry/stop/target lines on the chart):
  ... --direction short --entry 1.1450 --stop 1.1480 --target 1.1416,1.1357

--format square (1080x1080) | portrait (1080x1350) | wide (1200x675)
"""

import argparse
import csv
import io
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch


# ---------- data ----------

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


def swing_levels(candles, lookback=3, n=2):
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


# ---------- theme ----------

BG = "#0d1117"
PANEL = "#161b22"
GRID = "#222a35"
TEXT = "#e6edf3"
MUTED = "#8b949e"
UP = "#16c784"
DOWN = "#ea3943"
ACCENT = {"bullish": "#16c784", "bearish": "#ea3943", "neutral": "#8b949e"}
ARROW = {"bullish": "▲", "bearish": "▼", "neutral": "◆"}

FORMATS = {"square": (1080, 1080), "portrait": (1080, 1350), "wide": (1200, 675)}


def draw_candles(ax, view):
    width = 0.62
    for i, c in enumerate(view):
        color = UP if c["close"] >= c["open"] else DOWN
        ax.plot([i, i], [c["low"], c["high"]], color=color, linewidth=1.0, zorder=2,
                solid_capstyle="round")
        lo = min(c["open"], c["close"])
        ax.add_patch(Rectangle((i - width / 2, lo), width, abs(c["close"] - c["open"]) or 1e-9,
                               facecolor=color, edgecolor=color, linewidth=0.5, zorder=3))


def render(args):
    candles = load_candles(args.csv)
    if len(candles) < 10:
        raise SystemExit(f"only {len(candles)} candles parsed; need >= 10")
    closes = [c["close"] for c in candles]
    s20 = sma(closes, 20)
    s50 = sma(closes, 50)

    auto_sup, auto_res = swing_levels(candles)
    sup = [float(v) for v in args.support.split(",") if v.strip()] if args.support else auto_sup
    res = [float(v) for v in args.resistance.split(",") if v.strip()] if args.resistance else auto_res

    setup = None
    if args.entry or args.stop or args.target:
        setup = {"entry": float(args.entry) if args.entry else None,
                 "stop": float(args.stop) if args.stop else None,
                 "targets": [float(v) for v in args.target.split(",") if v.strip()] if args.target else []}

    bias = (args.bias or "neutral").lower()
    acc = ACCENT.get(bias, MUTED)
    price = float(args.price) if args.price else closes[-1]

    W, H = FORMATS.get(args.format, FORMATS["square"])
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor(BG)

    # layout fractions (x0, y0, w, h)
    is_wide = args.format == "wide"
    if is_wide:
        head_y, head_h = 0.80, 0.16
        ax_box = [0.06, 0.20, 0.62, 0.58]
        side_x = 0.70
    else:
        head_y, head_h = 0.84, 0.12
        ax_box = [0.07, 0.30, 0.86, 0.50]
        side_x = None

    # ----- header -----
    fig.text(0.07, head_y + head_h * 0.45, args.symbol, color=TEXT,
             fontsize=46 if not is_wide else 40, fontweight="bold", va="center", ha="left")
    fig.text(0.07, head_y + head_h * 0.05, f"{args.timeframe}   ·   {args.asof}",
             color=MUTED, fontsize=15, va="center", ha="left")

    # bias pill (top-right)
    pill = FancyBboxPatch((0.66, head_y + head_h * 0.18), 0.27, head_h * 0.6,
                          boxstyle="round,pad=0.012,rounding_size=0.04",
                          transform=fig.transFigure, facecolor=acc, edgecolor="none", zorder=5)
    fig.add_artist(pill)
    fig.text(0.795, head_y + head_h * 0.48, f"{ARROW.get(bias)}  {bias.upper()}",
             color="#0d1117", fontsize=22, fontweight="bold", va="center", ha="center", zorder=6)

    # ----- chart -----
    ax = fig.add_axes(ax_box)
    ax.set_facecolor(PANEL)
    bars = min(70, len(candles))
    start = len(candles) - bars
    view = candles[start:]
    x = list(range(len(view)))
    draw_candles(ax, view)
    if any(v is not None for v in s20[start:]):
        ax.plot(x, s20[start:], color="#58a6ff", linewidth=1.4, alpha=0.9, zorder=4)
    if any(v is not None for v in s50[start:]):
        ax.plot(x, s50[start:], color="#d29922", linewidth=1.4, alpha=0.9, zorder=4)

    lo = min(c["low"] for c in view)
    hi = max(c["high"] for c in view)
    extra = []
    if setup:
        extra = [v for v in [setup["entry"], setup["stop"]] + setup["targets"] if v]
    ymin = min([lo] + extra)
    ymax = max([hi] + extra)
    pad = (ymax - ymin) * 0.08 or 1e-4
    ymin -= pad
    ymax += pad

    def inr(v):
        return ymin <= v <= ymax

    for lv in res:
        if inr(lv):
            ax.axhline(lv, color=DOWN, linestyle=(0, (4, 3)), linewidth=1, alpha=0.55, zorder=1)
            ax.text(len(view) - 0.5, lv, f" {lv:g}", color=DOWN, va="center", fontsize=10, alpha=0.9)
    for lv in sup:
        if inr(lv):
            ax.axhline(lv, color=UP, linestyle=(0, (4, 3)), linewidth=1, alpha=0.55, zorder=1)
            ax.text(len(view) - 0.5, lv, f" {lv:g}", color=UP, va="center", fontsize=10, alpha=0.9)

    if setup:
        if setup["entry"] and inr(setup["entry"]):
            ax.axhline(setup["entry"], color="#58a6ff", linewidth=1.6, zorder=5)
        if setup["stop"] and inr(setup["stop"]):
            ax.add_patch(Rectangle((0, min(setup["entry"], setup["stop"])), len(view),
                                   abs(setup["entry"] - setup["stop"]), facecolor=DOWN, alpha=0.10, zorder=0))
            ax.axhline(setup["stop"], color=DOWN, linewidth=1.3, zorder=5)
        for t in setup["targets"]:
            if t and inr(t):
                ax.add_patch(Rectangle((0, min(setup["entry"], t)), len(view),
                                       abs(setup["entry"] - t), facecolor=UP, alpha=0.08, zorder=0))

    ax.axhline(price, color=TEXT, linestyle=":", linewidth=1, alpha=0.6, zorder=4)
    ax.set_ylim(ymin, ymax)
    ax.margins(x=0.02)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.set_xticks([])
    ax.grid(True, color=GRID, alpha=0.4, linewidth=0.6)

    # ----- stats row -----
    def chip(xc, label, value, color=TEXT):
        fig.text(xc, 0.205, label, color=MUTED, fontsize=12, ha="center", va="center")
        fig.text(xc, 0.165, value, color=color, fontsize=19, fontweight="bold", ha="center", va="center")

    # show the single nearest level each side of price (keeps the row uncluttered)
    res_above = sorted([r for r in res if r >= price])
    sup_below = sorted([s for s in sup if s <= price], reverse=True)
    res_txt = f"{(res_above[0] if res_above else (max(res) if res else 0)):g}" if res else "—"
    sup_txt = f"{(sup_below[0] if sup_below else (min(sup) if sup else 0)):g}" if sup else "—"
    if not is_wide:
        chip(0.205, "PRICE", f"{price:g}", TEXT)
        chip(0.405, "RESISTANCE", res_txt, DOWN)
        chip(0.605, "SUPPORT", sup_txt, UP)
        chip(0.805, "CONVICTION", args.conviction or "—", acc)
    else:
        chip(0.79, "PRICE", f"{price:g}", TEXT)
        fig.text(0.70, 0.50, "RESISTANCE", color=MUTED, fontsize=12, ha="left")
        fig.text(0.70, 0.45, res_txt, color=DOWN, fontsize=18, fontweight="bold", ha="left")
        fig.text(0.70, 0.37, "SUPPORT", color=MUTED, fontsize=12, ha="left")
        fig.text(0.70, 0.32, sup_txt, color=UP, fontsize=18, fontweight="bold", ha="left")

    # separator + footer
    fig.add_artist(plt.Line2D([0.07, 0.93], [0.115, 0.115], color=GRID, linewidth=1,
                              transform=fig.transFigure))
    fig.text(0.07, 0.075, args.handle or "", color=MUTED, fontsize=13, ha="left", va="center",
             fontweight="bold")
    fig.text(0.93, 0.075, "Analiza, nije finansijski savjet", color=MUTED, fontsize=11,
             ha="right", va="center", style="italic")

    fig.savefig(args.out, facecolor=BG)
    print(f"Card saved: {args.out}  ({W}x{H}, bias={bias})")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--symbol", default="")
    p.add_argument("--timeframe", default="")
    p.add_argument("--bias", default="neutral")
    p.add_argument("--conviction", default="")
    p.add_argument("--support", default="")
    p.add_argument("--resistance", default="")
    p.add_argument("--price", default="")
    p.add_argument("--asof", default="")
    p.add_argument("--handle", default="")
    p.add_argument("--direction", default="")
    p.add_argument("--entry", default="")
    p.add_argument("--stop", default="")
    p.add_argument("--target", default="")
    p.add_argument("--format", default="square", choices=list(FORMATS))
    p.add_argument("--out", required=True)
    render(p.parse_args())


if __name__ == "__main__":
    main()
