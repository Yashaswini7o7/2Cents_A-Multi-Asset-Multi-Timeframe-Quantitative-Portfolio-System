# Replication Guide

This document explains how to run the local replication test and how to adapt to real broker sandboxes.

## Local replication (quick)
1. Run simulator:
   `python -m src.simulator.sandbox_simulator --config configs/config.yaml --run_id run_local_001 --duration 60`
   This writes:
   - results/run_local_001_market.ndjson
   - results/run_local_001_order.ndjson
   - results/run_local_001_fill.ndjson
   - results/run_local_001_signal.ndjson

2. Replay:
   `python -m src.__main__ replay --market_log results/run_local_001_market.ndjson --config configs/config.yaml --out_dir results/replay_run_local_001`

3. Compare:
   `python -m src.tools.compare_runs results/run_local_001 results/replay_run_local_001 results/results.json`

## Move to real sandboxes
- Replace the simulator with live broker adapters:
  - Implement dataclients that stream raw events to the same ndjson market log format
  - Ensure all timestamps are UTC ISO8601 with microsecond precision
  - Use the same DeterministicExecutionModel configuration during live run and replay
