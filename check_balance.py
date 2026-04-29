#!/usr/bin/env python3
"""
Show current Dogecoin account balance and gain/loss so far.
Uses the same Coinbase API and INITIAL_CAPITAL_USD ($1000) from mvp.py.

External fiat (ACH/card transfers) is not in the bot's trade table. This script:
  - Optionally infers USD deposits from unexplained jumps between stored trade balances
    (heuristic — disable with SKIP_DEPOSIT_INFERENCE=1 if wrong).
  - Adds EXTERNAL_USD_DEPOSITS (dollars) from the environment to cost basis for adjusted P&L.
"""

import os
import argparse
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv
from trade_executor import CoinbaseTradeExecutor
from mvp import DogecoinAnalyzer, INITIAL_CAPITAL_USD
from database import TradingDatabase

# Defensive: mvp clamps, but avoid div-by-zero if this module is imported in isolation.
INITIAL_PORTFOLIO_VALUE = float(INITIAL_CAPITAL_USD) if float(INITIAL_CAPITAL_USD) > 0 else 1000.0


def _parse_trade_ts_local(ts):
    """Parse DB trade timestamp to naive local datetime (matches datetime.now() comparisons)."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        dt = ts
    else:
        s = str(ts).strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            if len(s) >= 19:
                try:
                    dt = datetime.fromisoformat(s[:19])
                except ValueError:
                    return None
            else:
                return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def _coerce_naive_local(dt):
    if dt is None:
        return None
    if isinstance(dt, datetime) and dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt


def deposits_in_window(dep_events, start_dt, end_dt):
    """
    Sum inferred external USD whose attributed time falls in (start_dt, end_dt].
    Event times are midpoints between consecutive trade rows (see infer_external_usd_deposits).
    """
    if not dep_events or start_dt is None or end_dt is None:
        return 0.0
    start = _coerce_naive_local(start_dt)
    end = _coerce_naive_local(end_dt)
    if start is None or end is None:
        return 0.0
    total = 0.0
    for ts, amt in dep_events:
        t = _coerce_naive_local(ts)
        if t is None:
            continue
        if start < t <= end:
            total += float(amt)
    return total


# Standard lookbacks shown in "Performance by period". Each deposit is netted only on the
# **shortest** of these windows that contains its attributed time (avoids the same ACH hitting 30d and 90d).
STANDARD_LOOKBACK_DAYS = (1, 7, 10, 30, 90, 180, 365)


def _min_standard_lookback_days_containing(dep_ts, now):
    nowl = _coerce_naive_local(now)
    t = _coerce_naive_local(dep_ts)
    if nowl is None or t is None:
        return None
    best = None
    for days in STANDARD_LOOKBACK_DAYS:
        start = nowl - timedelta(days=days)
        if start < t <= nowl:
            best = days if best is None else min(best, days)
    return best


def deposits_for_period_lookback(dep_events, lookback_days, now):
    """Inflows to remove from return for this row: deposits whose shortest containing standard lookback == lookback_days."""
    total = 0.0
    for ts, amt in dep_events:
        try:
            a = float(amt)
        except (TypeError, ValueError):
            continue
        if a <= 0:
            continue
        if _min_standard_lookback_days_containing(ts, now) == lookback_days:
            total += a
    return total


def infer_external_usd_deposits(trades, abs_tol=5.0):
    """
    Estimate fiat USD deposited outside bot trades: unexplained increases in USD balance
    between consecutive snapshots (trade_executions rows).

    Skips boundaries where the previous row shows **no USD change** despite a **successful** trade — that
    usually means a bad snapshot in the DB, not a real deposit (avoids summing thousands of false "gaps").
    """
    if not trades:
        return 0.0, [], []

    def _f(x):
        try:
            return float(x) if x is not None else None
        except (TypeError, ValueError):
            return None

    total = 0.0
    details = []
    events = []
    for i in range(1, len(trades)):
        prev = trades[i - 1]
        cur = trades[i]
        pb = _f(prev["balance_usd_before"])
        ua = _f(prev["balance_usd_after"])
        ub = _f(cur["balance_usd_before"])
        if ua is None or ub is None or pb is None:
            continue
        # Previous row must have a coherent USD move if it "succeeded", else linking is unreliable.
        if prev["success"] and abs(ua - pb) < 1e-3:
            continue
        gap = ub - ua
        tol = max(abs_tol, 0.01 * abs(ua))
        if gap > tol:
            total += gap
            ts = (cur["timestamp"] or "")[:19].replace("T", " ")
            details.append((f"between trades (~{ts})", gap))
            t_prev = _parse_trade_ts_local(prev["timestamp"] if "timestamp" in prev.keys() else None)
            t_cur = _parse_trade_ts_local(cur["timestamp"] if "timestamp" in cur.keys() else None)
            if t_prev is not None and t_cur is not None and t_cur >= t_prev:
                evt_ts = t_prev + (t_cur - t_prev) / 2
            else:
                evt_ts = t_cur or t_prev
            if evt_ts is not None:
                events.append((evt_ts, gap))
    return total, details, events


def main():
    parser = argparse.ArgumentParser(description="Show live balances and DB-based performance.")
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Use .ci_trading_data.db instead of local trading_data.db for DB-based sections.",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Explicit SQLite DB path to use for DB-based sections.",
    )
    args = parser.parse_args()

    load_dotenv()
    if not os.getenv("COINBASE_API_KEY") or not (os.getenv("COINBASE_PRIVATE_KEY") or os.getenv("COINBASE_API_SECRET")):
        print("❌ Missing Coinbase API credentials in .env (COINBASE_API_KEY and COINBASE_PRIVATE_KEY or COINBASE_API_SECRET)")
        return

    try:
        executor = CoinbaseTradeExecutor()
    except ValueError as e:
        print(f"❌ {e}")
        return

    print()
    print("=" * 50)
    print("  DOGECOIN ACCOUNT BALANCE")
    print("=" * 50)

    usd = executor.get_usd_balance()
    doge = executor.get_dogecoin_balance()
    price = executor.get_current_price()

    if usd is None or doge is None:
        print("❌ Could not load USD or DOGE balance.")
        return
    if price is None or price <= 0:
        print("❌ Could not load DOGE price.")
        return

    doge_value_usd = doge * price
    total_value = usd + doge_value_usd
    usd_pct = (usd / total_value * 100) if total_value > 0 else 0
    doge_pct = (doge_value_usd / total_value * 100) if total_value > 0 else 0

    print()
    print("  Balances")
    print("  --------")
    print(f"  USD:        ${usd:,.2f}  ({usd_pct:.1f}%)")
    print(f"  DOGE:       {doge:,.2f}  (${doge_value_usd:,.2f}, {doge_pct:.1f}%)")
    print()
    print(f"  DOGE price: ${price:.6f}")
    print(f"  Portfolio value: ${total_value:,.2f}")
    print()

    # Gain/loss vs INITIAL_CAPITAL_USD (same baseline as mvp.py)
    gain_loss = total_value - INITIAL_PORTFOLIO_VALUE
    gain_loss_pct = (gain_loss / INITIAL_PORTFOLIO_VALUE) * 100

    print(f"  Gain / Loss (vs ${INITIAL_PORTFOLIO_VALUE:,.0f} initial — ignores external deposits)")
    print("  --------------------------------")
    if gain_loss >= 0:
        print(f"  Gain:  ${gain_loss:+,.2f}  ({gain_loss_pct:+.2f}%)")
    else:
        print(f"  Loss:  ${gain_loss:,.2f}  ({gain_loss_pct:.2f}%)")
    print()
    print(f"  (Initial capital ${INITIAL_PORTFOLIO_VALUE:,.0f} — matches mvp.py INITIAL_CAPITAL_USD)")
    print("=" * 50)
    print()

    # Detailed performance by period: simple portfolio return per window
    try:
        analyzer = DogecoinAnalyzer()
    except Exception as e:
        print(f"⚠️  Could not initialize analyzer for performance: {e}")
        return

    # Override DB source when requested (default behavior remains local trading_data.db).
    db_override = None
    if args.db:
        db_override = str(Path(args.db).expanduser().resolve())
    elif args.ci:
        db_override = str((Path(__file__).resolve().parent / ".ci_trading_data.db").resolve())

    if db_override:
        try:
            # Close default DB opened by analyzer, then switch to the requested one.
            if analyzer.db:
                try:
                    analyzer.db.close()
                except Exception:
                    pass
            analyzer.db = TradingDatabase(db_override)
            analyzer.database_enabled = True
        except Exception as e:
            print(f"⚠️  Could not switch database to {db_override}: {e}")
            return

    if not analyzer.database_enabled or not analyzer.db:
        print("⚠️  Database not enabled - cannot compute period performance.")
        return

    now = datetime.now()
    current_value = total_value

    # --- External USD deposits: infer from trade ledger gaps + optional env ---
    all_trades = analyzer.db.get_all_trades()
    skip_infer = os.getenv("SKIP_DEPOSIT_INFERENCE", "").lower() in ("1", "true", "yes")
    if skip_infer:
        inferred_dep, dep_details, dep_events = 0.0, [], []
    else:
        inferred_dep, dep_details, dep_events = infer_external_usd_deposits(all_trades)
    try:
        manual_dep = float(os.getenv("EXTERNAL_USD_DEPOSITS", "0") or 0)
    except ValueError:
        manual_dep = 0.0
    total_dep = inferred_dep + manual_dep
    adjusted_basis = INITIAL_PORTFOLIO_VALUE + total_dep
    adj_gain = current_value - adjusted_basis
    adj_pct = (adj_gain / adjusted_basis) * 100 if adjusted_basis > 0 else 0.0

    print("  External USD deposits (excluded from naive gain above)")
    print("  ---------------------------------------------------------")
    if skip_infer:
        print("  Inferred from balance gaps:                      (off — SKIP_DEPOSIT_INFERENCE=1)")
    else:
        print(f"  Inferred from balance gaps in bot trade history:  ${inferred_dep:,.2f}")
    if manual_dep:
        print(f"  Manual (env EXTERNAL_USD_DEPOSITS):               ${manual_dep:,.2f}")
    else:
        print("  Manual (env EXTERNAL_USD_DEPOSITS):               $0.00  (set if inference misses deposits)")
    print(f"  Total treated as external capital:                ${total_dep:,.2f}")
    print()
    if total_dep > 0:
        print("  Gain / Loss vs adjusted basis (trading + market after external capital)")
        print("  --------------------------------------------------------------")
        if adj_gain >= 0:
            print(
                f"  Gain:  ${adj_gain:+,.2f}  ({adj_pct:+.2f}%)  (basis ${adjusted_basis:,.0f} = ${INITIAL_PORTFOLIO_VALUE:,.0f} + deposits)"
            )
        else:
            print(
                f"  Loss:  ${adj_gain:,.2f}  ({adj_pct:.2f}%)  (basis ${adjusted_basis:,.0f} = ${INITIAL_PORTFOLIO_VALUE:,.0f} + deposits)"
            )
        if dep_details and inferred_dep > 0:
            print("  Inferred deposit events (subset):")
            for label, amt in dep_details[:8]:
                print(f"    • {label}: +${amt:,.2f}")
            if len(dep_details) > 8:
                print(f"    … and {len(dep_details) - 8} more")
    else:
        print("  Adjusted P&L: same as naive (no deposits applied). Add EXTERNAL_USD_DEPOSITS or enable inference.")
    print()

    print("  Performance by period (return net of ext. USD — each inflow nets on shortest lookback row only)")
    print("  --------------------------------------------------------------------------------")
    period_defs = [
        ("1 day", 1),
        ("1 week (7d)", 7),
        ("10 days", 10),
        ("1 month (30d)", 30),
        ("3 months (90d)", 90),
        ("6 months (180d)", 180),
        ("1 year (365d)", 365),
    ]

    # Reuse trades list from above for period lookups
    from datetime import datetime as dt_class

    if all_trades:
        first_trade = all_trades[0]
        fts = dt_class.fromisoformat(first_trade["timestamp"].replace("Z", "+00:00")) if isinstance(
            first_trade["timestamp"], str
        ) else first_trade["timestamp"]
        first_trade_ts = _coerce_naive_local(fts)
    else:
        first_trade_ts = None

    # Helper: compute portfolio value at a given date using recorded balances and historical price
    def get_value_from_balances_at(start_dt_local):
        if not all_trades:
            return None
        start_dt_local = _coerce_naive_local(start_dt_local)
        # Find the last trade at or before start_dt_local
        latest = None
        latest_ts = None
        for t in all_trades:
            ts = dt_class.fromisoformat(t["timestamp"].replace("Z", "+00:00")) if isinstance(
                t["timestamp"], str
            ) else t["timestamp"]
            ts = _coerce_naive_local(ts)
            if ts is None:
                continue
            if ts <= start_dt_local and (latest_ts is None or ts > latest_ts):
                latest = t
                latest_ts = ts
        if latest is None:
            return None
        usd_after = latest["balance_usd_after"] or 0.0
        doge_after = latest["balance_doge_after"] or 0.0
        try:
            price_data = analyzer.fetch_historical_price_at_timestamp(start_dt_local)
        except Exception:
            price_data = None
        if not price_data:
            # Fallback: use recorded trade price
            start_price = latest["current_price"] or 0.0
        else:
            start_price = price_data.get("close", 0.0)
        if start_price <= 0:
            return None
        return usd_after + doge_after * start_price

    use_deposit_net = not skip_infer and bool(dep_events)

    # Windowed returns (subtract in-window inferred deposits from numerator — not TWR, but removes deposit inflation)
    for label, ndays in period_defs:
        start_dt = now - timedelta(days=ndays)
        from_first_trade = bool(first_trade_ts and start_dt < first_trade_ts)
        # Calendar start predates first trade: mark-to-market at first trade is often not comparable to
        # INITIAL_CAPITAL_USD in .env. When we know external USD, use full capital basis (initial + deposits).
        if from_first_trade and total_dep > 0 and adjusted_basis > 0:
            start_value = float(adjusted_basis)
            pct = (current_value - start_value) / start_value * 100.0
            symbol = "📈" if pct > 0 else "📉" if pct < 0 else "➡️"
            extra = "  [start = initial + external USD; lookback predates first trade]"
            print(f"  {label:<16}*: {symbol} {pct:+6.2f}%{extra}  (start ${start_value:,.0f} → now ${current_value:,.0f})")
            continue

        if from_first_trade:
            start_value = get_value_from_balances_at(first_trade_ts)
            if not start_value or start_value <= 0:
                start_value = float(INITIAL_PORTFOLIO_VALUE)
        else:
            start_value = get_value_from_balances_at(start_dt)
        if not start_value or start_value <= 0:
            continue
        dep_flow = deposits_for_period_lookback(dep_events, ndays, now) if use_deposit_net else 0.0
        pct_gross = (current_value - start_value) / start_value * 100.0
        naive_delta = current_value - start_value
        pct = (naive_delta - dep_flow) / start_value * 100.0
        # When calendar lookback starts before our first snapshot, naive_delta can be smaller than
        # summed gap-inferred deposits (deposits interact with traded capital); simple (E−S−D)/S misleads.
        deposit_net_skipped = False
        if (
            from_first_trade
            and use_deposit_net
            and dep_flow > 1.0
            and dep_flow > naive_delta + 50.0
        ):
            pct = pct_gross
            dep_flow = 0.0
            deposit_net_skipped = True
        symbol = "📈" if pct > 0 else "📉" if pct < 0 else "➡️"
        extra = ""
        if use_deposit_net and dep_flow >= 1.0:
            extra += f"  [subtract ~${dep_flow:,.0f} ext. USD inflow assigned to this lookback]"
        if use_deposit_net and abs(pct_gross - pct) > 0.15 and not deposit_net_skipped:
            extra += f"  (gross return {pct_gross:+.2f}% before that adjustment)"
        if deposit_net_skipped:
            extra += "  [gross only: deposit series vs first-trade baseline is ambiguous]"
        star = "*" if from_first_trade else ""
        print(f"  {label:<16}{star}: {symbol} {pct:+6.2f}%{extra}  (start ${start_value:,.0f} → now ${current_value:,.0f})")

    # Year-to-date (from Jan 1 or first trade)
    year_start = dt_class(now.year, 1, 1)
    if not first_trade_ts or year_start < first_trade_ts:
        ytd_start = first_trade_ts
    else:
        ytd_start = year_start

    if ytd_start:
        try:
            ytd_result = analyzer.get_portfolio_value_at_date(ytd_start, all_trades=all_trades)
        except Exception:
            ytd_result = None
        if ytd_result:
            _, _, ytd_start_value, _ = ytd_result
            if ytd_start_value > 0:
                # get_portfolio_value_at_date replays from INITIAL_CAPITAL_USD; wrong .env (e.g. $1) breaks YTD start.
                use_full_basis_ytd = (
                    total_dep > 0
                    and adjusted_basis > 0
                    and ytd_start_value < 0.15 * adjusted_basis
                )
                if use_full_basis_ytd:
                    basis = float(adjusted_basis)
                    ytd_pct = (current_value - basis) / basis * 100.0
                    symbol = "📈" if ytd_pct > 0 else "📉" if ytd_pct < 0 else "➡️"
                    yextra = "  [start = initial + external USD; YTD replay baseline not trusted]"
                    print(
                        f"  Year-to-date    : {symbol} {ytd_pct:+6.2f}%{yextra}  "
                        f"(start ${basis:,.0f} → now ${current_value:,.0f})"
                    )
                else:
                    y0 = _coerce_naive_local(ytd_start)
                    ytd_dep = deposits_in_window(dep_events, y0, now) if use_deposit_net else 0.0
                    ytd_gross = (current_value - ytd_start_value) / ytd_start_value * 100.0
                    ytd_pct = (current_value - ytd_start_value - ytd_dep) / ytd_start_value * 100.0
                    symbol = "📈" if ytd_pct > 0 else "📉" if ytd_pct < 0 else "➡️"
                    yextra = ""
                    if use_deposit_net and ytd_dep >= 1.0:
                        yextra += f"  [subtract ~${ytd_dep:,.0f} ext. USD inflow in YTD window]"
                    if use_deposit_net and abs(ytd_gross - ytd_pct) > 0.15:
                        yextra += f"  (gross return {ytd_gross:+.2f}% before that adjustment)"
                    print(
                        f"  Year-to-date    : {symbol} {ytd_pct:+6.2f}%{yextra}  "
                        f"(start ${ytd_start_value:,.0f} → now ${current_value:,.0f})"
                    )

    # All time: only show vs full capital basis (initial + external USD). Omit naive INITIAL-only row — it
    # misleads when INITIAL_CAPITAL_USD does not match real starting equity (e.g. $1 in .env).
    if total_dep > 0:
        all_adj_pct = (current_value - adjusted_basis) / adjusted_basis * 100.0
        sym2 = "📈" if all_adj_pct > 0 else "📉" if all_adj_pct < 0 else "➡️"
        print(
            f"  All time        : {sym2} {all_adj_pct:+6.2f}%  "
            f"(start ${adjusted_basis:,.0f} → now ${current_value:,.0f})  [initial ${INITIAL_PORTFOLIO_VALUE:,.0f} + ${total_dep:,.0f} external USD]"
        )
    else:
        all_start_value = INITIAL_PORTFOLIO_VALUE
        all_pct = (current_value - all_start_value) / all_start_value * 100.0
        symbol = "📈" if all_pct > 0 else "📉" if all_pct < 0 else "➡️"
        print(
            f"  All time        : {symbol} {all_pct:+6.2f}%  "
            f"(start ${all_start_value:,.0f} → now ${current_value:,.0f})  [no external deposits inferred]"
        )
    print()
    print(
        "  Note: Inferred deposit time ≈ midpoint between the two trades bracketing the USD gap; each inflow is"
    )
    print(
        "  subtracted only on the shortest standard lookback (1d…365d) that contains that time (not repeated on"
    )
    print(
        "  longer rows). Manual EXTERNAL_USD_DEPOSITS has no per-date split — it adjusts basis above, not these"
    )
    print("  windows. SKIP_DEPOSIT_INFERENCE=1 uses gross returns (no inflow subtraction).")
    print(
        "  * = lookback starts before first trade; start and % use full capital (INITIAL_CAPITAL_USD + external USD)"
    )
    print("    when deposits are known — avoids bogus .env initial in replayed snapshots.")
    print()


if __name__ == "__main__":
    main()
