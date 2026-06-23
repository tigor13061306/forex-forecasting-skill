#!/usr/bin/env python3
"""Append a forecast to the accuracy archive and copy its card there.

Run this right after generating a bias card so every call is recorded for later
review. It copies the card into <dir>/ as YYYY-MM-DD_SYMBOL_bias.png and appends a
row to <dir>/forecast_log.csv (creating the header on first use).

Example:
  python log_forecast.py --dir ./forecasts --symbol EURUSD --timeframe D1 \
      --price 1.14146 --bias bearish --conviction medium \
      --support "1.1409;1.1357" --resistance "1.1416;1.1450;1.1474" \
      --invalidation "daily close above 1.1416" --image eurusd_card.png
"""

import argparse
import csv
import datetime as dt
import os
import shutil

HEADER = ["date", "symbol", "timeframe", "price_at_forecast", "bias", "conviction",
          "support", "resistance", "invalidation", "image",
          "outcome", "checked_on", "notes"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="forecasts")
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", default="D1")
    p.add_argument("--price", required=True)
    p.add_argument("--bias", required=True)
    p.add_argument("--conviction", default="")
    p.add_argument("--support", default="")
    p.add_argument("--resistance", default="")
    p.add_argument("--invalidation", default="")
    p.add_argument("--image", default="", help="path to the card PNG to archive")
    p.add_argument("--date", default=dt.date.today().isoformat())
    args = p.parse_args()

    os.makedirs(args.dir, exist_ok=True)
    log = os.path.join(args.dir, "forecast_log.csv")

    image_name = ""
    if args.image and os.path.exists(args.image):
        image_name = f"{args.date}_{args.symbol}_bias.png"
        shutil.copyfile(args.image, os.path.join(args.dir, image_name))

    new = not os.path.exists(log)
    with open(log, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(HEADER)
        w.writerow([args.date, args.symbol, args.timeframe, args.price, args.bias,
                    args.conviction, args.support, args.resistance, args.invalidation,
                    image_name, "", "", ""])
    print(f"Logged {args.symbol} {args.bias} @ {args.price} -> {log}")
    if image_name:
        print(f"Archived card -> {os.path.join(args.dir, image_name)}")


if __name__ == "__main__":
    main()
