import pandas as pd
from collections import defaultdict
import numpy as np

class DataHandler:
    """
    Keeps tick buffers and can build bars deterministically.
    Stores bar_cache[symbol][timeframe] -> DataFrame
    """
    def __init__(self):
        self.tick_buffers = defaultdict(list)
        self.bar_cache = defaultdict(dict)

    def ingest_tick(self, tick):
        # tick must have 'symbol' and 'ts' and 'price' and 'size'
        sym = tick['symbol']
        self.tick_buffers[sym].append(tick)

    def build_bars(self, symbol, timeframe='1min'):
        # timeframe string pandas-compatible, e.g. '1min', '1H'
        df = pd.DataFrame(self.tick_buffers[symbol])
        if df.empty:
            return None
        # ensure datetime
        df['ts'] = pd.to_datetime(df['ts'])
        df = df.set_index('ts').sort_index()
        if 'price' not in df.columns:
            return None
        ohlc = df['price'].resample(timeframe).ohlc()
        vol = df['size'].resample(timeframe).sum().rename('volume')
        bars = pd.concat([ohlc, vol], axis=1).dropna()
        self.bar_cache[symbol][timeframe] = bars
        return bars

    def get_last_bar(self, symbol, timeframe='1min'):
        if timeframe not in self.bar_cache[symbol]:
            self.build_bars(symbol, timeframe)
        bars = self.bar_cache[symbol].get(timeframe)
        if bars is None or bars.empty:
            return None
        row = bars.iloc[-1]
        # return dict with open/high/low/close/volume
        return {'open': float(row['open']), 'high': float(row['high']),
                'low': float(row['low']), 'close': float(row['close']),
                'volume': float(row['volume']), 'ts': bars.index[-1].isoformat()}
