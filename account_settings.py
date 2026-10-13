"""Separate account-mode settings. No implicit public/local fallback."""
from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class AccountSettings:
    origin:str
    database_url:str
    state_secret:str
    issuer:str=''
    client_id:str=''
    client_secret:str=''
    demo:bool=False

    def __post_init__(self):
        parsed=urlsplit(self.origin)
        if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path or '*' in parsed.netloc):raise ValueError('Exact origin required')
        if self.demo:
            if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or not parsed.port:
                raise ValueError('Sample staging is loopback-only')
        elif parsed.scheme!='https':raise ValueError('Account mode requires HTTPS')
        if len(self.state_secret)<32:raise ValueError('Long state signing secret required')
        if not self.database_url:raise ValueError('Account database URL required')
        if not self.demo:
            issuer=urlsplit(self.issuer)
            if issuer.scheme!='https' or not issuer.hostname or issuer.username or issuer.password or issuer.query or issuer.fragment:
                raise ValueError('HTTPS OpenID issuer required')
            if not self.client_id or not self.client_secret:raise ValueError('OpenID client configuration required')

    @classmethod
    def from_environment(cls):
        return cls(origin=os.environ.get('ACCOUNTS_ORIGIN',''),database_url=os.environ.get('ACCOUNTS_DATABASE_URL',''),
                   state_secret=os.environ.get('ACCOUNTS_STATE_SECRET',''),issuer=os.environ.get('ACCOUNTS_OIDC_ISSUER',''),
                   client_id=os.environ.get('ACCOUNTS_OIDC_CLIENT_ID',''),client_secret=os.environ.get('ACCOUNTS_OIDC_CLIENT_SECRET',''))

    @classmethod
    def staging(cls):
        import secrets
        database=Path(__file__).with_name('accounts-staging.db').as_posix()
        return cls(origin='http://127.0.0.1:8001',database_url='sqlite:///'+database,state_secret=secrets.token_urlsafe(48),demo=True)
