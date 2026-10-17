"""Provider-qualified asset identity; tickers alone are not identifiers."""
from dataclasses import dataclass, asdict
import re

# Retain segment MICs as supplied: they are distinct from the operating MIC.
US_EQUITY_MICS = frozenset(('XNYS', 'XNAS', 'XNGS', 'XNMS', 'XNCM', 'ARCX', 'XASE', 'BATS'))


@dataclass(frozen=True)
class Asset:
    asset_class: str
    provider: str
    symbol: str
    name: str
    exchange: str
    currency: str
    timezone: str

    def __post_init__(self):
        if self.asset_class not in ('crypto', 'stock', 'etf'):
            raise ValueError('Unsupported asset class')
        if self.provider not in ('coingecko', 'twelvedata', 'demo'):
            raise ValueError('Unsupported provider')
        if not re.fullmatch(r'[A-Za-z0-9.^_-]{1,100}', self.symbol):
            raise ValueError('Invalid provider symbol')
        if not re.fullmatch(r'[A-Z0-9]{4}', self.exchange):
            raise ValueError('Invalid exchange MIC')
        if not re.fullmatch(r'[A-Z]{3}', self.currency):
            raise ValueError('Invalid currency')
        if not self.name or len(self.name) > 300:
            raise ValueError('Invalid name')
        if self.asset_class == 'crypto':
            if self.provider != 'coingecko' or self.exchange != 'XCRY' or self.timezone != 'UTC':
                raise ValueError('Invalid crypto identity')
        elif self.provider not in ('twelvedata','demo') or self.exchange not in US_EQUITY_MICS or self.currency != 'USD' or self.timezone != 'America/New_York':
            raise ValueError('Only supported US USD listings are enabled')

    @property
    def id(self):
        return ':'.join((self.provider, self.asset_class, self.exchange, self.currency, self.symbol))

    def public(self):
        return dict(id=self.id, **asdict(self))


def crypto_asset(coin):
    # CoinGecko's ID (not its display ticker) is the provider symbol.
    return Asset('crypto', 'coingecko', coin['id'], coin['name'], 'XCRY', 'USD', 'UTC')
