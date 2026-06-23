---
name: forex-forecasting
description: >-
  Produce forex (FX) forecasts and trade setups from live MetaTrader data plus
  fundamental context, and render an attractive, social-media-ready bias card
  (dark candlestick graphic with the bias, key levels, and conviction) the user
  can post. Use whenever the user asks for a forecast, prediction, outlook, bias,
  directional view, analysis, or trade idea on any currency pair or metal (EUR/USD,
  GBP/USD, USD/JPY, XAU/USD gold, XAG/USD silver) — even if they just name an
  instrument ("EURUSD?") or ask "long or short". Also triggers for "analyze this
  pair", "key levels", "is gold bullish", multi-timeframe analysis, position
  sizing/risk, or "make a chart/graphic/card for Instagram or X". The directional
  bias is the headline output; a full trade setup is added only when asked.
  ANALYZES and PROPOSES only — never places, modifies, or closes trades; the user
  always executes manually.
---

# Forex Forecasting

Turn raw market data into a clear, decision-ready **bias**: which way price is
likely to lean, why, the key levels that matter, and a chart that shows it — so the
trader can see and trust the call. The reader wants a confident, well-reasoned view
backed by live data, not a data dump. A full trade setup is offered only when they
ask for one.

## Core principle: evidence first, opinion second

A forecast is only useful if it's grounded in what the market is actually doing.
Always pull live data before forming a view. Never invent prices, levels, or
indicator values — if you don't have the data, get it or say so. A wrong number
destroys trust faster than a hedged opinion.

## Safety boundary (non-negotiable)

This skill produces analysis and proposals **only**. Never call any tool that
places, modifies, or closes orders/positions (e.g. `place_market_order`,
`place_pending_order`, `modify_position`, `close_position`, `cancel_*`). Even if
the user says "just do it", explain that you'll lay out the setup and they execute
it themselves. Reading data (`get_candles_latest`, `get_account_info`,
`get_symbol_price`, `get_all_symbols`, `get_all_positions`) is fine and expected.

## Workflow

### 1. Resolve the instrument and gather data

Symbols in MetaTrader have no slash: `EURUSD`, `GBPUSD`, `USDJPY`, `XAUUSD` (gold),
`XAGUSD` (silver). If the user wrote "EUR/USD" or "gold", map it. If unsure a symbol
exists, check with `get_all_symbols`.

Pull candles across **three timeframes** so you can align the big picture with an
entry. A reliable default:

- **D1** (daily) — the dominant trend and major levels. Get ~120 candles.
- **H4** (4-hour) — intermediate structure. Get ~120 candles.
- **H1** (hourly) — timing and near-term levels. Get ~120 candles.

For scalping requests lean to H1/M15; for swing/position requests lean to W1/D1/H4.
Use `get_candles_latest(symbol_name, timeframe, count)`. The result is CSV with
columns `time, open, high, low, close, tick_volume, spread, real_volume`.

Also pull `get_symbol_price` for the current bid/ask and live spread, and — if the
user wants a sized setup — `get_account_info` for balance, currency, and leverage.

### 2. Compute the technicals with the bundled script

Rather than eyeball candles or re-derive indicators by hand every time, save each
timeframe's CSV and run `scripts/ta.py` on it. The script computes SMA(20/50/200),
EMA(20/50), RSI(14), MACD, ATR(14), recent swing highs/lows (support &
resistance), and a trend classification, and prints them as JSON. This keeps the
numbers consistent and frees you to focus on interpretation.

```bash
python scripts/ta.py --csv d1.csv --symbol EURUSD --timeframe D1
```

It also sizes positions:

```bash
python scripts/ta.py --position-size --balance 99980 --risk-pct 1 \
  --entry 1.1430 --stop 1.1380 --symbol EURUSD
```

Read `scripts/ta.py` if you need to adjust parameters or understand a number.

### 3. Read the technical picture

Synthesize, don't just list. The questions to answer:

- **Trend:** Where is price relative to the 50/200 MAs on D1 and H4? Higher highs/
  higher lows or the reverse? Is the trend aligned across timeframes (strong) or
  conflicting (choppy, lower conviction)?
- **Momentum:** What do RSI and MACD say — overbought/oversold, divergence,
  momentum building or fading?
- **Key levels:** The swing highs/lows from the script are your support/resistance.
  Identify the nearest level above and below current price; these anchor entries,
  stops, and targets.
- **Volatility:** ATR tells you how far price typically moves — use it to set
  realistic stops and targets, not arbitrary round numbers.

### 4. Add the fundamental layer

Technicals tell you *what*; fundamentals tell you *why* and *what could blow up the
chart*. Use `WebSearch` to check for high-impact catalysts in the relevant window:
upcoming central-bank decisions, rate expectations, CPI/NFP/GDP releases, and the
prevailing macro narrative for each currency in the pair. For gold, watch real
yields, the dollar, and risk sentiment.

Keep it focused: the trader needs to know "is there a red-folder event in the next
day or two that makes this setup risky?" and "does the macro backdrop support or
fight my technical bias?". If a major event is imminent, say so prominently — it
can override an otherwise clean technical setup. If web access fails or returns
nothing usable, say the fundamental check was limited rather than inventing events.

### 5. Form the bias

The headline deliverable is a clear **directional bias**: bullish, bearish, or
neutral-range, with a plain statement of conviction (high / medium / low) and the
reasons behind it. This is what the trader is asking for — lead with it, state it
unambiguously, and back it with the evidence from steps 3–4.

Always name the **invalidation**: the price level or event that would flip the
bias. A bias the market can't prove wrong is useless; the invalidation is what
makes it actionable and honest about uncertainty.

Keep the focus on the bias and the levels. Only lay out a full trade setup (entry,
stop, take-profit, position size) if the user actually asks for one — e.g. "give me
a setup", "where do I enter", "size it for 1% risk". For a plain "what's your bias"
or "is gold bullish", don't bolt on an unsolicited setup; the levels and
invalidation are enough. When a setup *is* requested, size it with `ta.py` using
account info and anchor the stop beyond a real level plus an ATR buffer.

### 6. Make the shareable bias card (always)

A bias lands harder when the trader can *see* it — and traders love to post their
calls. Always produce an attractive, social-media-ready **bias card**: a polished
dark-theme graphic with the styled candlestick chart, a bold bias badge, the key
levels, conviction, and the current price. Use the bundled `scripts/card.py`:

```bash
python scripts/card.py --csv d1.csv --symbol EURUSD --timeframe "D1 · Dnevni bias" \
  --bias bearish --conviction Medium --asof 23.06.2026 --price 1.1428 \
  --support 1.1416,1.1357 --resistance 1.1474,1.1565 \
  --handle "@yourhandle" --format square --out eurusd_card.png
```

Pass the `--bias`, `--conviction`, and the same levels you cite in the report so the
card and the text agree. Card the timeframe that best represents the bias horizon
(D1 for swing, H1 for an intraday/daily bias). `--format` is `square` (1080×1080,
default — best for Instagram/X), `portrait` (1080×1350), or `wide` (1200×675).
`--handle` is optional (a watermark for the poster). The card always carries an
"Analiza, nije finansijski savjet" footer. If a setup was requested, also pass
`--direction/--entry/--stop/--target` to draw those levels on the card.

Save the PNG alongside the report and present it to the user — the card is the
headline visual, not an extra.

**Optional detailed chart.** When the user wants a closer analyst view (e.g. "show
me all three timeframes" or to annotate a setup in detail), also use
`scripts/chart.py`, which renders a plain multi-panel candlestick chart:

```bash
python scripts/chart.py --csv d1.csv,h4.csv,h1.csv --timeframe D1,H4,H1 \
  --symbol EURUSD --bias bearish --out eurusd_mtf.png
# setup overlay: --direction short --entry 1.327 --stop 1.3305 --target 1.3185,1.3163
```

## Output format

Write the report in the **language of the user's request** (if they wrote in
Bosnian/Croatian/Serbian, respond in that language). Lead with the bias, then the
chart, then the supporting detail:

```
# [SYMBOL] Bias — [horizon, e.g. "daily" or "next 1–3 days"]

**Bias:** [Bullish / Bearish / Neutral-range] · **Conviction:** [High/Medium/Low]
**Current price:** [bid/ask] · **Spread:** [x] · **As of:** [date/time]

[Bias card: the generated PNG (scripts/card.py), shown to the user.]

## Why
[Trend across the relevant timeframes, momentum, what the levels and ATR say —
prose, synthesized. The case for the bias.]

## Key levels
- Resistance: [levels]
- Support: [levels]

## Fundamental context
[High-impact events in the window, macro backdrop. Flag imminent red-folder events
prominently — they can override a clean technical bias.]

**Invalidation:** [the level/event that flips the bias]

[Trade setup section — ONLY if the user asked for one:
**Setup — [Long/Short]:** Entry [zone] · Stop [price] · Target(s) [price(s)] ·
R:R [ratio] · Size [lots] at [risk%] of [balance]]

---
*Analysis only — not financial advice. You execute any trade yourself.*
```

Adapt sensibly to scope: a quick "is gold bullish?" still gets a grounded bias, a
chart, and the levels that matter — just don't bloat every section.

## Quality bar

Before sending, sanity-check: Do the levels make sense relative to the current
price (support below, resistance above)? Is the stop on the correct side of entry?
Does R:R actually compute? Did you pull real data this session rather than relying
on memory? Is the fundamental window current (use today's date)? Catching a flipped
level or a stale price here is what separates a useful forecast from a misleading
one.
