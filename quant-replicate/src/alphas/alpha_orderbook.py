class AlphaOrderbook:
    def __init__(self, symbol, imbalance_threshold=0.2):
        self.symbol = symbol
        self.imbalance_threshold = imbalance_threshold
    def on_book(self, book, ts):
        bid_vol = sum([b['size'] for b in book.get('bids',[])])
        ask_vol = sum([a['size'] for a in book.get('asks',[])])
        if bid_vol + ask_vol == 0:
            return None
        imb = (bid_vol - ask_vol)/(bid_vol + ask_vol)
        if imb > self.imbalance_threshold:
            return {'alpha':'alpha_5_orderbook','signal':'buy_aggressive','size':1,'symbol':self.symbol,'ts':ts}
        if imb < -self.imbalance_threshold:
            return {'alpha':'alpha_5_orderbook','signal':'sell_aggressive','size':1,'symbol':self.symbol,'ts':ts}
        return None
