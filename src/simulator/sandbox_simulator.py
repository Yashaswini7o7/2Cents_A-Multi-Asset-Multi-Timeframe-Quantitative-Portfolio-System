"""
Simulate a deterministic 'sandbox' run that:
- creates synthetic tick and L2 market events for symbols
- runs the same alphas and OrderManager in a live mode
- writes ndjson logs: market, order, fill, signal
This allows a local end-to-end replication test.
"""
import argparse, os, json, random, time
from datetime import datetime, timedelta, timezone
from framework.logger import setup_logger
from framework.execution_model import DeterministicExecutionModel
from framework.order_manager import OrderManager
from framework.datahandler import DataHandler
from alphas.alpha_pairs import AlphaPairs
from alphas.alpha_breakout import AlphaBreakout
from alphas.alpha_mtf import AlphaMTF
from alphas.alpha_multiasset import AlphaMultiAsset
from alphas.alpha_orderbook import AlphaOrderbook

logger = setup_logger('sim')

def iso_now(ts):
    return ts.isoformat().replace('+00:00','Z')

def ndjson_writer(path, obj):
    with open(path,'a') as f:
        f.write(json.dumps(obj, default=str) + '\\n')

def generate_tick(symbol, base_price, ts, vol=1.0):
    # deterministic modified price based on ts.second for variability
    price = round(base_price * (1 + 0.0001*(ts.second % 30 - 15)), 4)
    return {'msg_type':'tick','symbol':symbol,'ts':iso_now(ts),'price':price,'size':vol}

def generate_l2(symbol, base_price, ts):
    # produce small L2 snapshot deterministic
    bids = [[round(base_price * (1 - 0.0001*i),4), 10 + i] for i in range(3)]
    asks = [[round(base_price * (1 + 0.0001*i),4), 12 + i] for i in range(3)]
    return {'msg_type':'l2_update','symbol':symbol,'ts':iso_now(ts),'bids': [{'price':b[0],'size':b[1]} for b in bids],
            'asks':[{'price':a[0],'size':a[1]} for a in asks]}

def create_simulated_run(cfg, run_id='run_local_001', duration_seconds=60):
    """
    Runs a deterministic sandbox for duration_seconds (small for testing).
    Writes market_log, order_log, fill_log and signal_log under results/.
    """
    base_out = cfg['storage']['base_path']
    os.makedirs(base_out, exist_ok=True)
    market_path = os.path.join(base_out, f"{run_id}_market.ndjson")
    order_path = os.path.join(base_out, f"{run_id}_order.ndjson")
    fill_path = os.path.join(base_out, f"{run_id}_fill.ndjson")
    signal_path = os.path.join(base_out, f"{run_id}_signal.ndjson")
    # remove existing files
    for p in (market_path, order_path, fill_path, signal_path):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass

    # deterministic seed
    seed = cfg.get('seed', 0)
    random.seed(seed)

    # symbols and base prices
    symbols = ['SYM_A','SYM_B','SYM_C','SYM_D','SYM_E']
    base_prices = {'SYM_A':100.0,'SYM_B':98.0,'SYM_C':150.0,'SYM_D':50.0,'SYM_E':200.0}

    # prepare components
    exec_model = DeterministicExecutionModel(slippage_abs=cfg['backtest'].get('slippage_abs',0.0),
                                            slippage_pct=cfg['backtest'].get('slippage_pct',0.0),
                                            tick_size=0.01,lot_size=1.0,seed=seed)
    datahandler = DataHandler()
    om = OrderManager(exec_model, lambda o: ndjson_writer(order_path,o), lambda f: ndjson_writer(fill_path,f),
                      fee_per_trade=cfg['backtest'].get('commission_per_trade',0.0))

    # instantiate alphas (use same config)
    acfg = cfg.get('alphas',{})
    alpha1 = AlphaPairs('SYM_A','SYM_B', lookback=acfg.get('alpha_1_pairs',{}).get('lookback',60),
                        z_enter=acfg.get('alpha_1_pairs',{}).get('z_enter',2.0),
                        z_exit=acfg.get('alpha_1_pairs',{}).get('z_exit',0.5), seed=seed)
    alpha2 = AlphaBreakout('SYM_C', lookback=acfg.get('alpha_2_breakout',{}).get('lookback',20))
    alpha3 = AlphaMTF('SYM_D', fast=acfg.get('alpha_3_mtf',{}).get('fast',8), slow=acfg.get('alpha_3_mtf',{}).get('slow',34))
    alpha4 = AlphaMultiAsset(acfg.get('alpha_4_multi_asset',{}).get('symbols',['SYM_A','SYM_B','SYM_C']))
    alpha5 = AlphaOrderbook('SYM_E', imbalance_threshold=acfg.get('alpha_5_orderbook',{}).get('imbalance_threshold',0.2))

    # run deterministic ticks
    start_ts = datetime.utcnow().replace(tzinfo=timezone.utc)
    ts = start_ts
    end_ts = start_ts + timedelta(seconds=duration_seconds)
    logger.info("Simulator starting run %s from %s to %s", run_id, iso_now(start_ts), iso_now(end_ts))
    while ts < end_ts:
        for s in symbols:
            tick = generate_tick(s, base_prices[s], ts)
            ndjson_writer(market_path, tick)
            datahandler.ingest_tick(tick)
            # build 1min bars when ts.second == 0 (approx simulate)
            # simpler: attempt to get last bars and call alphas if possible
            bar_s = datahandler.get_last_bar(s, timeframe='1min')
            # pair alpha check
            bar_a = datahandler.get_last_bar(alpha1.symbol_a, timeframe='1min')
            bar_b = datahandler.get_last_bar(alpha1.symbol_b, timeframe='1min')
            if bar_a and bar_b:
                sig = alpha1.on_bar(bar_a, bar_b, tick['ts'])
                if sig:
                    ndjson_writer(signal_path, sig)
                    # process pair signal into two market orders
                    if sig['signal'] == 'short_a_long_b':
                        om.submit_market_order(sig['alpha'], alpha1.symbol_a, 'sell', 1, datahandler.get_last_bar(alpha1.symbol_a)['close'], tick['ts'])
                        om.submit_market_order(sig['alpha'], alpha1.symbol_b, 'buy', 1, datahandler.get_last_bar(alpha1.symbol_b)['close'], tick['ts'])
                    elif sig['signal'] == 'long_a_short_b':
                        om.submit_market_order(sig['alpha'], alpha1.symbol_a, 'buy', 1, datahandler.get_last_bar(alpha1.symbol_a)['close'], tick['ts'])
                        om.submit_market_order(sig['alpha'], alpha1.symbol_b, 'sell', 1, datahandler.get_last_bar(alpha1.symbol_b)['close'], tick['ts'])
            # breakout
            bar2 = datahandler.get_last_bar(alpha2.symbol, timeframe='1min')
            if bar2:
                sig2 = alpha2.on_bar(bar2, tick['ts'])
                if sig2:
                    ndjson_writer(signal_path, sig2)
                    om.submit_market_order(sig2['alpha'], sig2['symbol'], 'buy', sig2['size'], bar2['close'], tick['ts'])
            # MTF
            bar3 = datahandler.get_last_bar(alpha3.symbol, timeframe='1min')
            if bar3:
                sig3 = alpha3.on_bar_minute(bar3, tick['ts'])
                if sig3:
                    ndjson_writer(signal_path, sig3)
                    om.submit_market_order(sig3['alpha'], sig3['symbol'], 'buy' if sig3['signal']=='long' else 'sell', sig3['size'], bar3['close'], tick['ts'])
            # multiasset
            bars = {x: datahandler.get_last_bar(x, timeframe='1min') for x in alpha4.symbols}
            if any(bars.values()):
                sig4 = alpha4.on_bar(bars, tick['ts'])
                if sig4:
                    ndjson_writer(signal_path, sig4)
                    om.submit_market_order(sig4['alpha'], sig4['symbol'], 'buy', sig4['size'], bars[sig4['symbol']]['close'], tick['ts'])
            # l2 events for SYM_E every 5 seconds
            if ts.second % 5 == 0 and s == 'SYM_E':
                l2 = generate_l2('SYM_E', base_prices['SYM_E'], ts)
                ndjson_writer(market_path, l2)
                sig5 = alpha5.on_book({'bids': l2['bids'], 'asks': l2['asks']}, l2['ts'])
                if sig5:
                    ndjson_writer(signal_path, sig5)
                    # pick top price for SYM_E
                    top_price = l2['bids'][0]['price'] if sig5['signal'].startswith('buy') else l2['asks'][0]['price']
                    om.submit_market_order(sig5['alpha'], sig5['symbol'], 'buy' if sig5['signal'].startswith('buy') else 'sell', sig5['size'], top_price, l2['ts'])
        ts += timedelta(seconds=1)
    # write run metadata
    meta = {'run_id': run_id, 'seed': cfg.get('seed'), 'start_ts': iso_now(start_ts), 'end_ts': iso_now(end_ts)}
    ndjson_writer(os.path.join(cfg['storage']['base_path'], f"{run_id}_metadata.json"), meta)
    logger.info("Simulator finished run %s. market_log=%s", run_id, market_path)
    return {
        'market_log': market_path,
        'order_log': order_path,
        'fill_log': fill_path,
        'signal_log': signal_path,
        'metadata': os.path.join(cfg['storage']['base_path'], f"{run_id}_metadata.json")
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='configs/config.yaml')
    parser.add_argument('--run_id', default='run_local_001')
    parser.add_argument('--duration', type=int, default=60)
    args = parser.parse_args()
    import yaml
    with open(args.config,'r') as f:
        cfg = yaml.safe_load(f)
    out = create_simulated_run(cfg, run_id=args.run_id, duration_seconds=args.duration)
    print(json.dumps(out, indent=2))
