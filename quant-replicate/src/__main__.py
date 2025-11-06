"""
CLI entrypoints:
- replay: replay a market log into the backtest engine
- report: generate quantstats report (optional)
"""
import argparse, yaml, os
from framework.logger import setup_logger
from backtest.engine import BacktestEngine
from framework.replay import ReplayEngine
from backtest.quantstats_report import generate_report

logger = setup_logger('cli')

def load_config(path):
    with open(path,'r') as f:
        return yaml.safe_load(f)

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd')
    r = sub.add_parser('replay')
    r.add_argument('--config', default='configs/config.yaml')
    r.add_argument('--market_log', required=True)
    r.add_argument('--out_dir', default=None)
    args = p.parse_args()
    cfg = load_config(args.config)
    if args.cmd == 'replay':
        out_dir = args.out_dir or os.path.join(cfg['storage']['base_path'],'replay_'+os.path.basename(args.market_log).replace('.ndjson',''))
        os.makedirs(out_dir, exist_ok=True)
        logger.info('Starting replay: market_log=%s out_dir=%s', args.market_log, out_dir)
        re = ReplayEngine(args.market_log, seed=cfg.get('seed',0))
        be = BacktestEngine(cfg)
        be.run_replay(re, out_dir)
        logger.info('Replay completed, outputs in %s', out_dir)
    else:
        p.print_help()

if __name__ == '__main__':
    main()
