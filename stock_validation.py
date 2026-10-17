"""Provider-independent daily-bar validation; no persistence or network access."""
from datetime import date
import math
from stock_provider import StockDataError


def validate_bars(rows,start,end):
    """Normalize a complete provider result before it can enter research/cache."""
    output=[];seen=set()
    try:
        if not isinstance(rows,list):raise ValueError('Expected daily-bar list')
        for row in rows:
            if not isinstance(row,dict):raise ValueError('Expected daily-bar object')
            day=row['date']
            if not isinstance(day,str) or date.fromisoformat(day).isoformat()!=day or day in seen or not start<=day<=end:
                raise ValueError('Invalid, duplicate or out-of-window date')
            seen.add(day);bar={'date':day}
            for field in ('open','high','low','close','volume'):
                raw=row[field]
                if isinstance(raw,bool):raise ValueError('Boolean numeric value')
                value=float(raw)
                if not math.isfinite(value) or value<0 or (field!='volume' and value==0):raise ValueError('Invalid numeric value')
                bar[field]=value
            if not bar['low']<=min(bar['open'],bar['close'])<=max(bar['open'],bar['close'])<=bar['high']:
                raise ValueError('Inconsistent OHLC')
            output.append(bar)
    except (ValueError,TypeError,KeyError,OverflowError):
        raise StockDataError('stock_invalid','Stock history contains invalid, duplicate or out-of-window daily bars.') from None
    return sorted(output,key=lambda bar:bar['date'])
