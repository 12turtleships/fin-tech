# Run mvp.py every 6 hours

The analysis prompt in `mvp.py` tells the model that **trades run on this same ~6-hour automatic schedule** (no intraday bot between runs), so recommendations match how the system actually operates.

## 1. Runner script

- **Script:** `run_mvp.sh` (in this folder)
- It runs `python3 mvp.py` from `/Users/sungchun/projects/fin-tech` and appends output to `logs/mvp-YYYYMMDD.log`.

## 2. Add a cron job (every 6 hours)

Open crontab:

```bash
crontab -e
```

Add one of these lines (choose one):

**Run at 00:00, 06:00, 12:00, 18:00:**

```cron
0 */6 * * * /Users/sungchun/projects/fin-tech/run_mvp.sh
```

**Run at 03:00, 09:00, 15:00, 21:00:**

```cron
0 3,9,15,21 * * * /Users/sungchun/projects/fin-tech/run_mvp.sh
```

Save and exit. Cron will run the script every 6 hours.

## 3. Python environment (important for cron)

Cron runs with a minimal environment and does **not** see your terminal’s virtualenv or PATH. The 18:00 run failed with `ModuleNotFoundError: No module named 'requests'` for this reason.

- The script uses `venv/bin/python` or `.venv/bin/python` if present in `fin-tech`, otherwise `python3`.
- **Recommended:** create a venv in the project and install deps so cron uses it:
  ```bash
  cd /Users/sungchun/projects/fin-tech
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```
  Then cron will use `fin-tech/venv/bin/python` automatically.

## 4. Logs

- Logs are written to: `fin-tech/logs/mvp-YYYYMMDD.log`
- One file per day; new runs append to the same file.
- The script creates `logs/` if missing.

## 5. Test once

```bash
/Users/sungchun/projects/fin-tech/run_mvp.sh
```

Then check `logs/mvp-$(date +%Y%m%d).log`.
