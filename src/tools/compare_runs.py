"""
Compare sandbox run vs replay run and produce results.json according to required schema.
Usage:
  python -m src.tools.compare_runs <sandbox_dir_prefix> <replay_out_dir> <out_results_json>

sandbox_dir_prefix: path prefix used in simulator outputs, e.g. results/run_local_001
replay_out_dir: directory with 'fill_log.ndjson' and 'order_log.ndjson' created by backtest replay
"""
import json, os, sys
from collections import defaultdict
from datetime import datetime

"""def load_ndjson(path):
    items = []
    if not os.path.exists(path):
        return items
    with open(path,'r') as f:
        for line in f:
            if not line.strip(): continue
            items.append(json.loads(line))
    return items
    """

def load_ndjson(path):
    """
    Robust NDJSON loader.
    - If file missing -> returns empty list
    - For each physical line:
        * try json.loads(line) (fast path)
        * otherwise attempt to parse multiple JSON objects from the line using raw_decode
    - Skips empty lines and logs/parses as many valid objects as possible (best-effort).
    """
    items = []
    if not os.path.exists(path):
        return items
    decoder = json.JSONDecoder()
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for lineno, raw in enumerate(f, start=1):
            s = raw.strip()
            if not s:
                continue
            # Fast path: normal ndjson single object per line
            try:
                obj = json.loads(s)
                items.append(obj)
                continue
            except json.JSONDecodeError:
                pass
            # Fallback: try to decode multiple JSON objects from the same line
            idx = 0
            L = len(s)
            while idx < L:
                try:
                    obj, end = decoder.raw_decode(s, idx)
                except json.JSONDecodeError:
                    # cannot decode further from this line: log minimal info and break
                    # (we don't raise to allow other lines to be processed)
                    # Optionally: write a small debug message to stderr or to a .log file
                    # print(f"[load_ndjson] JSONDecodeError at {path}:{lineno} idx={idx}", file=sys.stderr)
                    break
                items.append(obj)
                idx = end
                # skip whitespace between consecutive objects
                while idx < L and s[idx].isspace():
                    idx += 1
    return items

def summarize_trades(fills):
    # group by alpha (order entries include alpha if logged by order manager)
    per_alpha = defaultdict(lambda: {'trades':0,'pnl':0.0})
    # naive pnl calc: for buys subtract price * size, for sells add price*size
    # but sandbox and replay must match exactly; this is a simple reproduction
    for fill in fills:
        # If fill has no alpha, try to infer from order_log(s) or include under unknown
        alpha = fill.get('alpha') or 'unknown'
        side = fill.get('side')
        price = float(fill.get('price',0.0))
        size = float(fill.get('size',0.0))
        amount = price * size
        if side in ('buy','long','buy_aggressive'):
            per_alpha[alpha]['pnl'] -= amount
        else:
            per_alpha[alpha]['pnl'] += amount
        per_alpha[alpha]['trades'] += 1
    return per_alpha

def compare(sandbox_prefix, replay_dir, out_path):
    # paths produced by simulator: <sandbox_prefix>_market.ndjson, <sandbox_prefix>_fill.ndjson, etc
    sandbox_market = sandbox_prefix + "_market.ndjson"
    sandbox_fill = sandbox_prefix + "_fill.ndjson"
    sandbox_order = sandbox_prefix + "_order.ndjson"
    replay_fill = os.path.join(replay_dir, 'fill_log.ndjson')
    replay_order = os.path.join(replay_dir, 'order_log.ndjson')

    s_fills = load_ndjson(sandbox_fill)
    r_fills = load_ndjson(replay_fill)

    # For exact matching we compare counts and per-trade fields
    portfolio_sandbox_pnl = sum([ (float(f.get('price',0.0))*float(f.get('size',0.0)) * (1 if f.get('side','sell') not in ('buy','long','buy_aggressive') else -1)) for f in s_fills ])
    portfolio_replay_pnl = sum([ (float(f.get('price',0.0))*float(f.get('size',0.0)) * (1 if f.get('side','sell') not in ('buy','long','buy_aggressive') else -1)) for f in r_fills ])

    pnl_match = "PASS" if abs(portfolio_sandbox_pnl - portfolio_replay_pnl) < 1e-8 else "FAIL"

    # group per-alpha using 'alpha' key if available, else 'unknown'
    def group_by_alpha(fills):
        d = {}
        for f in fills:
            alpha = f.get('alpha') or 'unknown'
            if alpha not in d:
                d[alpha] = {'trades':0, 'pnl':0.0, 'fills':[]}
            side = f.get('side')
            amt = float(f.get('price',0.0)) * float(f.get('size',0.0))
            pnl_delta = -amt if side in ('buy','long','buy_aggressive') else amt
            d[alpha]['trades'] += 1
            d[alpha]['pnl'] += pnl_delta
            d[alpha]['fills'].append(f)
        return d

    s_by_alpha = group_by_alpha(s_fills)
    r_by_alpha = group_by_alpha(r_fills)

    alphas_result = {}
    mismatch_reports = {}

    # union of alpha keys
    keys = set(list(s_by_alpha.keys())+list(r_by_alpha.keys()))
    for k in keys:
        sinfo = s_by_alpha.get(k, {'trades':0,'pnl':0.0,'fills':[]})
        rinfo = r_by_alpha.get(k, {'trades':0,'pnl':0.0,'fills':[]})
        match = "PASS" if (sinfo['trades']==rinfo['trades'] and abs(sinfo['pnl']-rinfo['pnl'])<1e-8) else "FAIL"
        analysis = ""
        if match == "FAIL":
            # create mismatch report
            diffs = []
            maxn = max(len(sinfo['fills']), len(rinfo['fills']))
            for i in range(maxn):
                sfill = sinfo['fills'][i] if i < len(sinfo['fills']) else None
                rfill = rinfo['fills'][i] if i < len(rinfo['fills']) else None
                diff = {'index': i, 'sandbox': sfill, 'replay': rfill}
                if sfill and rfill:
                    price_diff = float(sfill.get('price',0.0)) - float(rfill.get('price',0.0))
                    diff['price_diff'] = price_diff
                    if abs(price_diff) > 1e-9:
                        diff['likely_cause'] = 'price_mismatch'
                else:
                    diff['likely_cause'] = 'missing_fill'
                diffs.append(diff)
            report_path = os.path.join(os.path.dirname(out_path), f"mismatch_report_{k}.json")
            with open(report_path,'w') as f:
                json.dump(diffs, f, indent=2, default=str)
            mismatch_reports[k] = report_path
            analysis = f"See {report_path}"
        alphas_result[k] = {'trades': sinfo['trades'], 'pnl': round(sinfo['pnl'],8), 'match': match, 'analysis': analysis}

    results = {
        "metadata": {
            "compare_time": datetime.utcnow().isoformat() + 'Z'
        },
        "portfolio_pnl": {
            "sandbox_pnl": round(portfolio_sandbox_pnl,8),
            "backtest_pnl": round(portfolio_replay_pnl,8),
            "pnl_match": pnl_match
        },
        "alphas": alphas_result,
        "mismatch_reports": mismatch_reports
    }

    with open(out_path,'w') as f:
        json.dump(results, f, indent=2)

    print("Wrote results to", out_path)
    return results

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("usage: compare_runs <sandbox_prefix> <replay_dir> <out_path>")
        raise SystemExit(1)
    compare(sys.argv[1], sys.argv[2], sys.argv[3])
