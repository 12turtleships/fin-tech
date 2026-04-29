#!/usr/bin/env python3
"""
Reconcile live Coinbase balances against the latest DB trade snapshot.

Usage:
  python reconcile_balances.py
  python reconcile_balances.py --db /path/to/trading_data.db
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from database import TradingDatabase
from trade_executor import CoinbaseTradeExecutor


def _latest_trade_row(db_path: str):
    db = TradingDatabase(db_path)
    try:
        rows = db.get_recent_trades(limit=1)
        return rows[0] if rows else None
    finally:
        db.close()


def _print_snapshot(name: str, row, live_price: float, live_usd: float, live_doge: float):
    print(f"\n{name}")
    print("-" * len(name))
    if not row:
        print("No trade rows found in this DB.")
        return

    ts = row["timestamp"]
    action = (row["action"] or "").upper()
    pct = row["percentage"]
    usd_a = float(row["balance_usd_after"] or 0.0)
    doge_a = float(row["balance_doge_after"] or 0.0)
    trade_px = float(row["current_price"] or 0.0)

    value_trade_px = usd_a + doge_a * trade_px
    value_live_px = usd_a + doge_a * live_price
    delta_usd = live_usd - usd_a
    delta_doge = live_doge - doge_a
    implied_notional = abs(delta_doge) * live_price
    implied_side = "SELL" if delta_doge < 0 else ("BUY" if delta_doge > 0 else "NONE")

    print(f"Timestamp:          {ts}")
    print(f"Last action:        {action} {pct if pct is not None else '—'}%")
    print(f"After balances:     USD ${usd_a:,.2f}, DOGE {doge_a:,.8f}")
    print(f"Trade price:        ${trade_px:,.6f}")
    print(f"Value at trade px:  ${value_trade_px:,.2f}")
    print(f"Value at live px:   ${value_live_px:,.2f}")
    print()
    print(f"Delta vs live:      USD {delta_usd:+,.2f}, DOGE {delta_doge:+,.8f}")
    if implied_side != "NONE" and implied_notional >= 1.0:
        print(
            f"Inferred missing leg: likely {implied_side} {abs(delta_doge):,.2f} DOGE "
            f"(~${implied_notional:,.2f} at live price)"
        )
    else:
        print("Inferred missing leg: none (or below noise threshold)")


def main():
    parser = argparse.ArgumentParser(description="Compare live balances vs latest trade snapshot.")
    parser.add_argument(
        "--db",
        default=str(Path(__file__).resolve().parent / "trading_data.db"),
        help="SQLite DB path to reconcile against (default: local trading_data.db).",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Also compare against .ci_trading_data.db if present.",
    )
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parent / ".env")

    ex = CoinbaseTradeExecutor()
    live_usd = float(ex.get_usd_balance() or 0.0)
    live_doge = float(ex.get_dogecoin_balance() or 0.0)
    live_price = float(ex.get_current_price() or 0.0)
    live_value = live_usd + live_doge * live_price

    print("\nLIVE (Coinbase)")
    print("---------------")
    print(f"USD:              ${live_usd:,.2f}")
    print(f"DOGE:             {live_doge:,.8f}")
    print(f"DOGE price:       ${live_price:,.6f}")
    print(f"Portfolio value:  ${live_value:,.2f}")

    db_path = str(Path(args.db).expanduser().resolve())
    _print_snapshot(f"DB snapshot ({db_path})", _latest_trade_row(db_path), live_price, live_usd, live_doge)

    if args.ci:
        ci_path = Path(__file__).resolve().parent / ".ci_trading_data.db"
        if ci_path.is_file():
            _print_snapshot(
                f"DB snapshot ({ci_path})",
                _latest_trade_row(str(ci_path)),
                live_price,
                live_usd,
                live_doge,
            )
        else:
            print(f"\nDB snapshot ({ci_path})")
            print("-" * (14 + len(str(ci_path))))
            print("File not found.")


if __name__ == "__main__":
    main()

