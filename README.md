# quant-replicate

Deterministic, replayable multi-alpha quant framework with replication test.

This repository implements Track A (Full-Stack Quant). It includes:
- 5 alphas (pairs, breakout, MTF, multi-asset, orderbook)
- Deterministic ExecutionModel and OrderManager
- Sandbox simulator that writes canonical raw market logs (ndjson)
- Backtest replay that consumes identical market logs
- Comparator that produces `results/results.json` and mismatch reports
- Unit tests and a runbook for reproduction

## Quick local run (no external brokers)
1. Install dependencies (recommended in a virtualenv):
   ```bash
   pip install -r requirements.txt
   # OR with poetry:
   poetry install
   ```

2. Create results directory:
   ```bash
   mkdir -p results/market_logs results/order_logs results/fill_logs results/signal_logs
   ```

3. Run a full simulation (sandbox run) that generates logs:
   ```bash
   python -m src.simulator.sandbox_simulator --config configs/config.yaml --run_id run_local_001
   ```

4. Replay the exact logs:
   ```bash
   python -m src.__main__ replay --config configs/config.yaml --market_log results/market_logs/run_local_001_market.ndjson --out_dir results/replay_run_local_001
   ```

5. Compare sandbox vs backtest:
   ```bash
   python -m src.tools.compare_runs results/run_local_001 results/replay_run_local_001 results/results.json
   ```

6. Open `results/results.json` to inspect match PASS/FAIL info.

## Notes
- Replace the simulator with real broker adapters later; keep the log formats identical.
- All logs are newline-delimited JSON (ndjson) with UTC ISO8601 timestamps (microseconds).
