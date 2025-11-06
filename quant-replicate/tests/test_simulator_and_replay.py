import os, json, tempfile
from simulator.sandbox_simulator import create_simulated_run
from backtest.engine import BacktestEngine
from framework.replay import ReplayEngine

def test_end_to_end_local_replay():
    # Use config
    import yaml
    with open('configs/config.yaml','r') as f:
        cfg = yaml.safe_load(f)
    # small run
    run_info = create_simulated_run(cfg, run_id='test_run_001', duration_seconds=5)
    market_log = run_info['market_log']
    # replay
    out_dir = 'results/replay_test_run_001'
    if os.path.exists(out_dir):
        import shutil; shutil.rmtree(out_dir)
    re = ReplayEngine(market_log, seed=cfg.get('seed',0))
    be = BacktestEngine(cfg)
    be.run_replay(re, out_dir)
    # compare files exist
    assert os.path.exists(os.path.join(out_dir,'order_log.ndjson'))
    assert os.path.exists(os.path.join(out_dir,'fill_log.ndjson'))
