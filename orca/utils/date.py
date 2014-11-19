"""
.. moduleauthor:: Li, Wang <wangziqi@foreseefund.com>
"""

import pandas as pd

def to_datetime(dates):
    """Change a sequence of dates into datetime format."""
    return pd.to_datetime([str(date) for date in dates])

def to_datestr(dates):
    """Change a sequence of dates into 'yyyymmdd' string format."""
    try:
        return [date.strftime('%Y%m%d') for date in dates]
    except:
        return [str(date) for date in dates]

def to_dateint(dates):
    """Change a sequence of dates into yyyymmdd integer format."""
    try:
        return [date.year*10000+date.month*100+date.day \
                for date in dates]
    except:
        return [int(date) for date in dates]
