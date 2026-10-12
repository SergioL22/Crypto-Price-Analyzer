"""Read-only portfolio snapshot; no database writes or AI requests."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re

MAX_HOLDINGS = 100
MAX_PRICE_AGE_SECONDS = 900


def load_saved_portfolio():
    # CLI defaults to the project directory. Never accept a path from HTTP input.
    path = Path(__file__).resolve().parent / 'portfolio.json'
    try:
        with path.open(encoding='utf-8') as source:
            return json.load(source)
    except FileNotFoundError:
        return {}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Invalid number')
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError('Invalid number')
    return result


def positions(raw):
    if not isinstance(raw, dict) or len(raw) > MAX_HOLDINGS:
        raise ValueError('Invalid portfolio')
    result = []
    for coin_id, item in raw.items():
        if not isinstance(coin_id, str) or len(coin_id) > 100 or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', coin_id):
            raise ValueError('Invalid coin')
        if not isinstance(item, dict):
            raise ValueError('Invalid holding')
        amount = number(item.get('amount'))
        average = number(item.get('avg_buy_price', 0))
        if amount:
            cost = number(amount * average) if average else None
            result.append(dict(coin_id=coin_id, amount=amount,
                               average_buy_price_usd=average or None, cost_basis_usd=cost))
    return sorted(result, key=lambda item: item['coin_id'])


def snapshot(holdings, quotes, current):
    rows = []
    for holding in holdings:
        row = dict(holding, price_usd=None, price_updated_at_utc=None,
                   price_status='unavailable', value_usd=None, unrealized_pnl_usd=None,
                   allocation_pct=None)
        quote = quotes.get(holding['coin_id']) if isinstance(quotes, dict) else None
        try:
            price = number(quote['usd'])
            timestamp = number(quote['last_updated_at'])
            updated = datetime.fromtimestamp(timestamp, timezone.utc)
            age = (current - updated).total_seconds()
            if price <= 0 or age < -60:
                raise ValueError('Invalid quote')
            row['price_updated_at_utc'] = updated.isoformat()
            if age > MAX_PRICE_AGE_SECONDS:
                row['price_status'] = 'stale'
            else:
                value = number(price * holding['amount'])
                row.update(price_usd=price, value_usd=value, price_status='current')
                if holding['cost_basis_usd'] is not None:
                    row['unrealized_pnl_usd'] = value - holding['cost_basis_usd']
        except (TypeError, KeyError, ValueError, OverflowError, OSError):
            pass
        rows.append(row)
    priced = [row for row in rows if row['value_usd'] is not None]
    subtotal = number(math.fsum(row['value_usd'] for row in priced))
    complete = len(priced) == len(rows)
    known_costs = all(row['cost_basis_usd'] is not None for row in rows)
    for row in priced:
        row['allocation_pct'] = row['value_usd'] / subtotal * 100 if subtotal else None
    return dict(currency='usd', fetched_at_utc=current.isoformat(), holdings=rows,
                priced_holdings=len(priced), total_holdings=len(rows), complete=complete,
                priced_value_usd=subtotal, total_value_usd=subtotal if complete else None,
                unrealized_pnl_usd=math.fsum(row['unrealized_pnl_usd'] for row in rows) if complete and known_costs else None,
                limitations=['Quotes older than 15 minutes are excluded from valuation.',
                             'Allocation describes priced holdings only when prices are missing.',
                             'Zero or missing average buy price means unknown cost basis.',
                             'Unrealized gain/loss excludes fees, realized trades and cash flows.'])
