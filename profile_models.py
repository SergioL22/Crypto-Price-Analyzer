"""Optional metadata contracts, separate from market evidence and AI inputs."""
from typing import Literal
from backend_models import Contract


class CompanyProfileFields(Contract):
    name:str|None
    finnhub_industry:str|None
    headquarters_country:str|None
    reporting_currency:str|None
    website_url:str|None
    ipo_date:str|None


class CompanyProfileResponse(Contract):
    asset_id:str
    source:str
    status:Literal['available','setup_required','not_supported','not_found']
    message:str
    profile:CompanyProfileFields|None
    fetched_at_utc:str|None
    provider_updated_at_utc:str|None
    cache_hit:bool
    identity_scope:Literal['symbol_operating_exchange']|None
    missing_fields:list[str]
