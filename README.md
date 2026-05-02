# DOGE Trading Bot — AI-Powered Crypto Trading System

An end-to-end automated trading system for Dogecoin that combines real-time market data, technical analysis, and LLM-driven decision-making to execute trades on Coinbase Advanced. Runs continuously via GitHub Actions every 6 hours with a full audit trail stored in SQLite.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      GitHub Actions (every 6h)              │
│                                                             │
│  Market Data Layer          Analysis Layer    Execution     │
│  ┌───────────────┐         ┌──────────────┐  ┌──────────┐  │
│  │ Coinbase API  │──OHLCV─▶│  Technical   │  │Coinbase  │  │
│  │ (30d + 24h)   │         │  Indicators  │  │ Advanced │  │
│  └───────────────┘         │  RSI / MACD  │  │Trade API │  │
│  ┌───────────────┐         │  Bollinger   │  └────┬─────┘  │
│  │ Order Book    │──────▶  │  ATR / ADX   │       │        │
│  │ (bid/ask)     │         └──────┬───────┘       │        │
│  └───────────────┘                │               │        │
│  ┌───────────────┐         ┌──────▼───────┐       │        │
│  │ Fear & Greed  │──────▶  │  OpenAI LLM  │───────┘        │
│  │ Index         │         │  BUY/SELL/   │                 │
│  └───────────────┘         │  HOLD + %    │                 │
│                            └──────┬───────┘                 │
│                                   │                         │
│                            ┌──────▼───────┐                 │
│                            │  SQLite DB   │                 │
│                            │  Audit Trail │                 │
│                            └──────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Features

- **LLM-driven decisions** — sends structured market context to ChatGPT (GPT-4o), which returns a JSON recommendation with action, position size, confidence, and invalidation price
- **Mean-reversion strategy** — buys dips aggressively near Bollinger Band lower / 30-day support; sells rips near upper band / 30-day resistance
- **ATR-based position sizing** — automatically scales trade size to keep dollar-risk constant relative to current volatility
- **Full audit trail** — every market snapshot, AI analysis, and trade execution is stored in SQLite with before/after balances
- **Backtest & simulation** — replay the last N days using historical data without executing real trades
- **CI/CD scheduling** — GitHub Actions runs the full cycle every 6 hours; SQLite DB is cached between runs and uploaded as a downloadable artifact
- **Balance reconciliation** — detects discrepancies between live Coinbase balances and the local DB snapshot

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| AI / LLM | OpenAI API (GPT-4o) |
| Exchange | Coinbase Advanced Trade API (JWT auth) |
| Market Data | Coinbase Exchange public API, yfinance |
| Technical Analysis | `ta` library — Bollinger Bands, RSI, MACD, ATR, ADX |
| Sentiment | Fear & Greed Index, SerpAPI (news) |
| Storage | SQLite via custom ORM (`database.py`) |
| Scheduling | GitHub Actions (cron) |
| Auth | JWT / EC private key (PyJWT + cryptography) |

---

## System Flow

1. Fetch 30-day and 24-hour OHLCV candles from Coinbase
2. Fetch live order book (bid/ask spread, volume imbalance)
3. Retrieve current portfolio allocation (USD vs. DOGE)
4. Pull Fear & Greed Index and optional news sentiment
5. Compute 16 technical indicators (Bollinger Bands, RSI, MACD, ATR, ADX, MAs)
6. Build a structured prompt and send to ChatGPT
7. Parse the JSON recommendation (action, %, confidence, invalidation price)
8. Apply ATR-based position size cap and consecutive-BUY streak governance
9. Execute trade via Coinbase Advanced (market order, IOC)
10. Persist market snapshot + analysis + execution to SQLite

---

## Setup

### Prerequisites

- Python 3.11+
- Coinbase Advanced API credentials ([guide](https://docs.cdp.coinbase.com/advanced-trade/docs/getting-started))
- OpenAI API key

### Install

```bash
git clone https://github.com/12turtleships/fin-tech.git
cd fin-tech
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configure

Create a `.env` file in the repo root:

```env
# Required
OPENAI_API_KEY=sk-...
COINBASE_API_KEY=organizations/{org_id}/apiKeys/{key_id}
COINBASE_PRIVATE_KEY="-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----\n"

# Optional
SERPAPI_KEY=...
INITIAL_CAPITAL_USD=1000

# Trading behavior
TRADING_POSTURE=aggressive        # aggressive | balanced | conservative
FEE_GATE_MIN_PCT=0.75             # minimum BB fee-edge % to trade
CB_ATR_RISK_PCT=3.5               # % of capital at risk per trade (ATR sizing)
CONSECUTIVE_BUY_FORBID_AFTER=10   # max consecutive BUYs before forcing HOLD/SELL
CB_ENABLED=0                      # set 1 to enable circuit breakers
```

---

## Usage

```bash
# Full analysis + trade execution
python mvp.py

# Backtest last 7 days (no real trades)
python mvp.py --simulate

# Performance report
python mvp.py --analyze-performance 7

# Manual trade override
python mvp.py --manual-trade SELL 20

# View trade history (local DB)
python mvp.py --trades 50

# Sync CI database from GitHub Actions artifact and view history
python mvp.py --trades 50 --sync-github

# Live balance + P&L summary
python check_balance.py

# Compare live balance vs DB snapshot
python reconcile_balances.py --ci
```

---

## GitHub Actions (Cloud Scheduling)

The workflow at `.github/workflows/mvp-scheduled.yml` runs automatically every 6 hours at 00:20, 06:20, 12:20, 18:20 UTC — no local machine needed.

**Required repository secrets** (Settings → Secrets → Actions):

| Secret | Description |
|---|---|
| `OPENAI_API_KEY` | ChatGPT access |
| `COINBASE_API_KEY` | Coinbase Advanced API key path |
| `COINBASE_PRIVATE_KEY` | EC private key (full PEM, multi-line) |

Each run uploads the SQLite database as an artifact. Download it locally to inspect the full trade history:

```bash
# After downloading the artifact zip and extracting trading_data.db:
python mvp.py --trades 50 --db /path/to/trading_data.db
```

---

## Database Schema

| Table | Description |
|---|---|
| `market_data` | Price snapshots, technical indicators, order book, sentiment |
| `analysis_results` | Full LLM output — recommendation, confidence, reasoning, risk factors |
| `trade_executions` | Order lifecycle — amounts, before/after balances, order ID, status |
| `news_cache` | Daily news sentiment cache (minimizes SerpAPI cost) |

---

## Project Structure

```
fin-tech/
├── mvp.py                        # Core pipeline — data → analysis → execution
├── trade_executor.py             # Coinbase Advanced Trade API client
├── database.py                   # SQLite ORM and schema migrations
├── check_balance.py              # Live balance + DB performance report
├── reconcile_balances.py         # Live vs DB snapshot reconciliation
├── portfolio_analyzer.py         # 20-DMA shoulder strategy analyzer
├── automated_portfolio_analyzer.py  # Scheduled stock portfolio alerts
├── requirements.txt
└── .github/workflows/
    └── mvp-scheduled.yml         # GitHub Actions cron scheduler
```

---

## Disclaimer

This project is for educational and experimental purposes only. Cryptocurrency trading carries significant financial risk. Past performance does not guarantee future results. Always validate behavior in simulation mode before enabling real trade execution.
