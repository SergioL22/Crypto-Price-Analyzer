from copy import deepcopy
from datetime import datetime,timezone
import pytest
from account_research import SampleProvider
from stock_service import StockService
from stock_provider import StockDataError
from stock_validation import validate_bars

NOW=datetime(2026,10,16,21,tzinfo=timezone.utc)
ASSET='twelvedata:stock:XNYS:USD:DEMO'
BAR=dict(date='2026-10-15',open=10,high=12,low=9,close=11,volume=100)


@pytest.mark.parametrize('field,value',[
 ('close',True),('close',0),('close',-1),('close','nan'),('close','inf'),
 ('open',None),('volume',-1),('volume',False),('high',8),('low',13),
 ('date','2026-02-30'),('date','20261015'),('date','2026-10-17')])
def test_invalid_provider_values_are_rejected(field,value):
    bar=dict(BAR);bar[field]=value
    with pytest.raises(StockDataError) as error:validate_bars([bar],'2026-10-01','2026-10-16')
    assert error.value.code=='stock_invalid'


@pytest.mark.parametrize('rows',[None,{},'secret',[None],[{}],[BAR,BAR]])
def test_malformed_history_is_sanitized(rows):
    with pytest.raises(StockDataError) as error:validate_bars(rows,'2026-10-01','2026-10-16')
    assert 'secret' not in str(error.value)


def test_bars_normalize_sort_and_preserve_zero_volume_without_mutating_provider():
    rows=[dict(BAR,date='2026-10-16'),{k:str(v) for k,v in BAR.items()}]
    rows[1]['volume']='0';before=deepcopy(rows)
    result=validate_bars(rows,'2026-10-15','2026-10-16')
    assert rows==before and result[0]['date']=='2026-10-15'
    assert result[0]['volume']==0 and result[0]['close']==11
    assert validate_bars([],'2026-10-15','2026-10-16')==[]


class Provider(SampleProvider):
    def __init__(self,mode):self.mode=mode;self.calls=0
    def history(self,*args):
        self.calls+=1;rows=super().history(*args)
        if self.mode=='duplicate':rows.append(dict(rows[0]))
        elif self.mode=='invalid':rows[0]['close']=float('nan')
        elif self.mode=='reverse':rows.reverse()
        return rows


@pytest.mark.parametrize('mode',['duplicate','invalid'])
@pytest.mark.parametrize('cached',[True,False])
def test_every_provider_is_validated_before_cache_or_analysis(mode,cached):
    provider=Provider(mode);service=StockService(provider=provider)
    with pytest.raises(StockDataError):service.research(ASSET,90,NOW,use_cache=cached)
    provider.mode='valid'
    # A fresh research capture must not reuse a rejected browsing response.
    result=service.research(ASSET,90,NOW)
    assert result['window']['complete'] and result['indicators'] is not None
    assert provider.calls==2


def test_unsorted_provider_bars_produce_chronological_history_and_valid_cache():
    provider=Provider('reverse');service=StockService(provider=provider)
    result=service.research(ASSET,90,NOW,use_cache=True)
    assert result['window']['complete']
    dates=[bar['date'] for bar in result['bars']]
    assert dates==sorted(dates) and len(dates)==len(set(dates))
    assert service.research(ASSET,90,NOW,use_cache=True)['bars']==result['bars']
    assert provider.calls==1
