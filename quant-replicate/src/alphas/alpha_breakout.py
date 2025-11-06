from collections import deque

class AlphaBreakout:
    def __init__(self, symbol, lookback=20):
        self.symbol = symbol
        self.lookback = lookback
        self.highs = deque(maxlen=lookback)
    def on_bar(self, bar, ts):
        self.highs.append(bar['high'])
        if len(self.highs) < self.lookback:
            return None
        if bar['close'] > max(self.highs):
            return {'alpha': 'alpha_2_breakout', 'signal': 'long', 'size': 1, 'symbol': self.symbol, 'ts': ts}
        return None
