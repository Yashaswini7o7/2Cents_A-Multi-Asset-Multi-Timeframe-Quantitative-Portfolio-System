from datetime import timedelta, datetime, timezone

class Clock:
    def __init__(self):
        self.now = None

    def set(self, ts):
        # ts: datetime (aware UTC) or ISO string
        if isinstance(ts, str):
            self.now = datetime.fromisoformat(ts.replace('Z','+00:00'))
        else:
            self.now = ts

    def advance_to(self, ts):
        # set absolute time
        if isinstance(ts, str):
            self.now = datetime.fromisoformat(ts.replace('Z','+00:00'))
        else:
            self.now = ts

    def iso(self):
        return self.now.isoformat().replace('+00:00','Z')
