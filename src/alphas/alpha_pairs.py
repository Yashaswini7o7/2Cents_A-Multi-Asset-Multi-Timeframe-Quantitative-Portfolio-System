import numpy as np
from collections import deque

class AlphaPairs:
    """
    Pairs mean reversion alpha.
    on_bar(bar_a, bar_b, ts) -> signal dict or None
    """
    def __init__(self, symbol_a, symbol_b, lookback=60, z_enter=2.0, z_exit=0.5, seed=0):
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b
        self.lookback = lookback
        self.z_enter = z_enter
        self.z_exit = z_exit
        self.spread_hist = deque(maxlen=lookback)
        self.seed = seed
        import numpy as _np, random as _random
        _np.random.seed(seed); _random.seed(seed)

    def on_bar(self, bar_a, bar_b, ts):
        px_a = float(bar_a['close']); px_b = float(bar_b['close'])
        spread = px_a - px_b
        self.spread_hist.append(spread)
        if len(self.spread_hist) < self.lookback:
            return None
        arr = np.array(self.spread_hist)
        std = arr.std(ddof=0)
        if std == 0:
            return None
        z = (spread - arr.mean())/std
        if z > self.z_enter:
            return {'alpha': 'alpha_1_pairs', 'signal': 'short_a_long_b', 'size': 1, 'symbols': (self.symbol_a,self.symbol_b), 'ts': ts}
        if z < -self.z_enter:
            return {'alpha': 'alpha_1_pairs', 'signal': 'long_a_short_b', 'size': 1, 'symbols': (self.symbol_a,self.symbol_b), 'ts': ts}
        if abs(z) < self.z_exit:
            return {'alpha': 'alpha_1_pairs', 'signal': 'exit', 'ts': ts}
        return None
