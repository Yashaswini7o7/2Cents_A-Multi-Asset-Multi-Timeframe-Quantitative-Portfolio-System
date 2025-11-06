import os, json
from framework.execution_model import DeterministicExecutionModel
from framework.order_manager import OrderManager
from framework.datahandler import DataHandler
from framework.portfolio import Portfolio
from framework.logger import setup_logger, save_json
from alphas.alpha_pairs import AlphaPairs
from alphas.alpha_breakout import AlphaBreakout
from alphas.alpha_mtf import AlphaMTF
from alphas.alpha_multiasset import AlphaMultiAsset
from alphas.alpha_orderbook import AlphaOrderbook

logger = setup_logger('backtest')

class BacktestEngine:
    """
    BacktestEngine can run a replay (ReplayEngine.stream_events) and:
    - feed events to DataHandler
    - run all alphas on appropriate events (bars/ticks/book)
    - submit orders to OrderManager (deterministic) and write logs (order_log.ndjson, fill_log.ndjson)
    """
    def __init__(self, config: dict):
        self.config = config
        self.exec_model = DeterministicExecutionModel(
            slippage_abs=config['backtest'].get('slippage_abs',0.0),
            slippage_pct=config['backtest'].get('slippage_pct',0.0),
            tick_size=0.01, lot_size=1.0, seed=config.get('seed',0)
        )
        # writers
        self.order_log_path = None
        self.fill_log_path = None
        self.market_writer = None
        self.order_writer = None
        self.fill_writer = None
        self.datahandler = DataHandler()
        self.portfolio = Portfolio(initial_cash=config['backtest'].get('initial_cash',100000.0))
        # instantiate alphas using config
        acfg = config.get('alphas',{})
        self.alpha1 = AlphaPairs(acfg.get('alpha_1_pairs',{}).get('symbol_a','SYM_A'),
                                 acfg.get('alpha_1_pairs',{}).get('symbol_b','SYM_B'),
                                 lookback=acfg.get('alpha_1_pairs',{}).get('lookback',60),
                                 z_enter=acfg.get('alpha_1_pairs',{}).get('z_enter',2.0),
                                 z_exit=acfg.get('alpha_1_pairs',{}).get('z_exit',0.5),
                                 seed=config.get('seed',0))
        self.alpha2 = AlphaBreakout(acfg.get('alpha_2_breakout',{}).get('symbol','SYM_C'),
                                    lookback=acfg.get('alpha_2_breakout',{}).get('lookback',20))
        self.alpha3 = AlphaMTF(acfg.get('alpha_3_mtf',{}).get('symbol','SYM_D'),
                               fast=acfg.get('alpha_3_mtf',{}).get('fast',8),
                               slow=acfg.get('alpha_3_mtf',{}).get('slow',34))
        self.alpha4 = AlphaMultiAsset(acfg.get('alpha_4_multi_asset',{}).get('symbols',['SYM_A','SYM_B','SYM_C']))
        self.alpha5 = AlphaOrderbook(acfg.get('alpha_5_orderbook',{}).get('symbol','SYM_E'),
                                     imbalance_threshold=acfg.get('alpha_5_orderbook',{}).get('imbalance_threshold',0.2))

    def _make_writers(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        self.market_log_path = os.path.join(out_dir,'market_replayed.ndjson')
        self.order_log_path = os.path.join(out_dir,'order_log.ndjson')
        self.fill_log_path = os.path.join(out_dir,'fill_log.ndjson')
        # open files and write via append
        def mw(obj):
            with open(self.market_log_path,'a') as f:
                f.write(json.dumps(obj, default=str) + '\\n')
        def ow(obj):
            with open(self.order_log_path,'a') as f:
                f.write(json.dumps(obj, default=str) + '\\n')
        def fw(obj):
            with open(self.fill_log_path,'a') as f:
                f.write(json.dumps(obj, default=str) + '\\n')
        self.market_writer = mw
        self.order_writer = ow
        self.fill_writer = fw
        # Setup order manager with deterministic exec model
        self.order_manager = OrderManager(self.exec_model, self.order_writer, self.fill_writer,
                                          fee_per_trade=self.config['backtest'].get('commission_per_trade',0.0))

    def run_replay(self, replay_engine, out_dir):
        logger.info('BacktestEngine: starting replay -> out_dir: %s', out_dir)
        self._make_writers(out_dir)
        # stream events
        for ev in replay_engine.stream_events():
            # write raw event to market writer
            self.market_writer(ev)
            # handle event types
            mtype = ev.get('msg_type','tick')
            ts = ev['ts']
            if mtype == 'tick':
                # ingest tick
                self.datahandler.ingest_tick(ev)
                # run orderbook alpha if book available? no
                # run breakout/mtf periodically via built bars: for simplicity, run all alphas when possible
                # Build 1min bars and feed
                bar = self.datahandler.get_last_bar(ev['symbol'], timeframe='1min')
                # For alpha 1 pairs, need both bars for A and B; try to get last bars for both
                bar_a = self.datahandler.get_last_bar(self.alpha1.symbol_a, timeframe='1min')
                bar_b = self.datahandler.get_last_bar(self.alpha1.symbol_b, timeframe='1min')
                if bar_a and bar_b:
                    sig = self.alpha1.on_bar(bar_a, bar_b, ts)
                    if sig:
                        self._process_signal(sig, ev)
                # alpha2 breakout operates on single symbol
                bar2 = self.datahandler.get_last_bar(self.alpha2.symbol, timeframe='1min')
                if bar2:
                    sig2 = self.alpha2.on_bar(bar2, ts)
                    if sig2:
                        self._process_signal(sig2, ev)
                # alpha3 uses minute bars
                bar3 = self.datahandler.get_last_bar(self.alpha3.symbol, timeframe='1min')
                if bar3:
                    sig3 = self.alpha3.on_bar_minute(bar3, ts)
                    if sig3:
                        self._process_signal(sig3, ev)
                # alpha4 uses bars snapshot
                bars = {s: self.datahandler.get_last_bar(s, timeframe='1min') for s in self.alpha4.symbols}
                if any(bars.values()):
                    sig4 = self.alpha4.on_bar(bars, ts)
                    if sig4:
                        self._process_signal(sig4, ev)
            elif mtype == 'l2_update':
                # pass to orderbook alpha
                book = {'bids': ev.get('bids',[]), 'asks': ev.get('asks',[])}
                sig5 = self.alpha5.on_book(book, ts)
                if sig5:
                    self._process_signal(sig5, ev)

        # after replay, save metadata and portfolio data for reporting
        meta = {
            'exec_model': self.exec_model.snapshot(),
            'seed': self.config.get('seed')
        }
        save_json_path = os.path.join(out_dir, 'replay_metadata.json')
        with open(save_json_path, 'w') as f:
            json.dump(meta, f, indent=2)

    def _process_signal(self, sig, ev):
        """
        Convert signal to deterministic market order and apply via order_manager.
        For pairs alpha, we synthesize two orders (long/short pair).
        """
        alpha = sig.get('alpha','unknown')
        ts = sig.get('ts', ev.get('ts'))
        if alpha == 'alpha_1_pairs':
            # pair trade: map signal to two market orders at current top_price (last tick price)
            symbol_a, symbol_b = sig['symbols']
            # obtain top prices from last ticks (simple: use last known tick price)
            last_tick_a = None
            last_tick_b = None
            # look into tick buffers
            la = self._last_tick_price(symbol_a)
            lb = self._last_tick_price(symbol_b)
            if la is None or lb is None:
                return
            if sig['signal'] == 'short_a_long_b':
                # short A -> sell A; long B -> buy B
                self.order_manager.submit_market_order(alpha, symbol_a, 'sell', sig['size'], la, ts)
                self.order_manager.submit_market_order(alpha, symbol_b, 'buy', sig['size'], lb, ts)
            elif sig['signal'] == 'long_a_short_b':
                self.order_manager.submit_market_order(alpha, symbol_a, 'buy', sig['size'], la, ts)
                self.order_manager.submit_market_order(alpha, symbol_b, 'sell', sig['size'], lb, ts)
            elif sig['signal'] == 'exit':
                # exit logic omitted as a no-op for deterministic example
                pass
        else:
            # single-symbol signals
            symbol = sig.get('symbol') or ev.get('symbol')
            top_price = self._last_tick_price(symbol)
            if top_price is None:
                return
            side_map = {
                'long':'buy','short':'sell',
                'buy_aggressive':'buy','sell_aggressive':'sell'
            }
            side = side_map.get(sig.get('signal'), 'buy')
            self.order_manager.submit_market_order(alpha, symbol, side, sig.get('size',1), top_price, ts)

    def _last_tick_price(self, symbol):
        # quick lookup from datahandler buffers
        buf = self.datahandler.tick_buffers.get(symbol, [])
        if not buf:
            return None
        return buf[-1]['price']
