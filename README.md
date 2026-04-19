# fin-tech

Dogecoin analysis and trading bot centered on `mvp.py`, with local/CI scheduling, SQLite history, and optional trade execution through Coinbase Advanced.

## What This Repo Does

- Fetches DOGE market data (30d + 24h), order book, sentiment, and account allocation.
- Computes technical indicators (including Bollinger Bands, RSI, MACD, ATR, ADX).
- Uses an LLM to generate a structured `BUY` / `SELL` / `HOLD` recommendation.
- Optionally executes trades (or simulates if API execution is unavailable).
- Stores market snapshots, analyses, and executions in SQLite.
- Supports GitHub Actions scheduled runs and artifact-based DB sync for local inspection.

## Main Entry Point

- `mvp.py` - primary CLI for analysis, execution, reporting, and trade history.

## Prerequisites

- Python 3.11+ recommended
- Coinbase Advanced API credentials (for real execution)
- OpenAI API key (required by `mvp.py`)
- Optional: SerpAPI key

Install dependencies:

```bash
cd /Users/sungchun/projects/fin-tech
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

Create `.env` in repo root. Typical keys:

- `OPENAI_API_KEY` (required)
- `COINBASE_API_KEY` (required for real execution)
- `COINBASE_PRIVATE_KEY` (required for real execution)
- `SERPAPI_KEY` (optional)
- `INITIAL_CAPITAL_USD` (optional, defaults to 1000)
- `GITHUB_TOKEN` or `GH_TOKEN` (optional, for `--trades --sync-github`)

Trading behavior controls:

- `TRADING_POSTURE` - defaults to `aggressive` (set `balanced` to soften)
- `FEE_GATE_MIN_PCT` - optional fee-edge threshold override
- `CONSECUTIVE_BUY_FORBID_AFTER` - optional BUY streak cap override in prompt
- `CB_ENABLED` - defaults to `0` (set `1` to enable circuit breakers)

## Quick Start

Run a full analysis cycle:

```bash
python mvp.py
```

Useful CLI commands:

```bash
python mvp.py --simulate
python mvp.py --analyze-performance 7
python mvp.py --review-reflections
python mvp.py --generate-dataset 7 sqlite
python mvp.py --simulate-and-dataset 7 sqlite
python mvp.py --manual-trade SELL 20
python mvp.py --trades 50
python mvp.py --trades 50 --sync-github
```

## Trade History and CI Database Sync

`--trades` reads SQLite and now includes fallback decision history (including `HOLD`) when no executed trades exist.

Sync latest GitHub Actions DB artifact and show history:

```bash
python mvp.py --trades 50 --sync-github
```

After sync, you can default `--trades` to the downloaded file:

```bash
export REMOTE_TRADING_DATA_DB="/Users/sungchun/projects/fin-tech/.ci_trading_data.db"
```

## GitHub Actions Schedule

Workflow: `.github/workflows/mvp-scheduled.yml`

- Runs every 6 hours (`20 */6 * * *`, UTC)
- Caches `trading_data.db` between runs
- Uploads `trading_data_db` artifact each run

Required repository secrets:

- `OPENAI_API_KEY`
- `COINBASE_API_KEY`
- `COINBASE_PRIVATE_KEY`

Optional secrets:

- `SERPAPI_KEY`
- `INITIAL_CAPITAL_USD`

## Data Storage

SQLite DB (default `trading_data.db`) tables include:

- `market_data`
- `analysis_results`
- `trade_executions`
- `news_cache`

## Related Docs

- `CRON_MVP.md` - local cron + GitHub Actions runbook
- `README_Dogecoin_Analyzer.md` - Dogecoin analyzer details
- `README_Trading_System.md` - trading-system notes
- `README_20DMA_Sell_Strategy.md` - alternate strategy notes
- `README_Automation.md` - legacy automation docs

## Notes

- This is high-risk software for educational/experimental use.
- Validate behavior in simulation before enabling real execution.
- Keep API keys and tokens out of version control.
