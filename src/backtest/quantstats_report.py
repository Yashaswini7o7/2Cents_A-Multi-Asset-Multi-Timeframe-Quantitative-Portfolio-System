import quantstats as qs
import pandas as pd

def generate_report(equity_series, out_html="results/quantstats.html"):
    """
    equity_series: pandas.Series indexed by datetime with equity values (floats)
    """
    qs.reports.html(equity_series, out_html)
