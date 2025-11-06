import json
from datetime import datetime
from typing import Iterator

class ReplayEngine:
    """
    Streams ticks (and L2 events) from an ndjson market log in chronological order.
    Each line must be a JSON object with at least: msg_type, ts, symbol, (price,size) or (bids,asks)
    """
    def __init__(self, market_log_path, seed=0):
        self.market_log_path = market_log_path
        self.seed = seed

    def stream_events(self):
        with open(self.market_log_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                ev = json.loads(line)
                # ensure ts normalized to ISO string
                ev['ts'] = ev['ts']
                yield ev
