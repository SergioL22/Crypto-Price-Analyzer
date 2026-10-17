"""Read-only research adapters: synthetic staging or explicit private live data."""
from datetime import datetime,timezone,timedelta
import math
import pandas as pd
import analysis
from assets import Asset,crypto_asset
from backend_service import AdmissionGate
from stock_service import StockService,session_window
from stock_provider import StockDataError
from account_store import AccountError

COINS=[crypto_asset(dict(id=coin,name=name,symbol=symbol)).public() for coin,name,symbol in
       [('bitcoin','Bitcoin','BTC'),('ethereum','Ethereum','ETH'),('solana','Solana','SOL')]]


def crypto_result(asset,frame,days,now):
    from history_window import select_daily_window
    frame,coverage=select_daily_window(frame,days,now=now-timedelta(days=1))
    if frame.empty:raise AccountError('history_unavailable',503)
    from price_validation import validate_prices
    frame=validate_prices(frame)
    prices=frame['price'];ma7=prices.rolling(7).mean();ma25=prices.rolling(25).mean()
    middle,upper,lower=analysis.compute_bollinger_bands(prices)
    finite=lambda value:float(value) if math.isfinite(value) else None
    points=[dict(date=date.date().isoformat(),price=float(price),ma_7=finite(ma7.iloc[i]),ma_25=finite(ma25.iloc[i]),
                 bollinger_lower=finite(lower.iloc[i]),bollinger_middle=finite(middle.iloc[i]),bollinger_upper=finite(upper.iloc[i])) for i,(date,price) in enumerate(prices.items())]
    indicators=None
    if len(prices)>=35 and not coverage['missing_days']:
        macd,signal,hist=analysis.compute_macd(prices)
        indicators=dict(rsi_14=finite(analysis.compute_rsi(prices)),ma_7=finite(ma7.iloc[-1]),ma_25=finite(ma25.iloc[-1]),
                        macd=finite(macd.iloc[-1]),macd_signal=finite(signal.iloc[-1]),macd_histogram=finite(hist.iloc[-1]))
    else:
        for point in points:
            for key in ('ma_7','ma_25','bollinger_lower','bollinger_middle','bollinger_upper'):point[key]=None
    return dict(asset=asset,history=points,bars=None,indicators=indicators,
                window=dict(observations=len(points),missing_sessions=[d.strftime('%Y-%m-%d') for d in pd.date_range(coverage['expected_start'],coverage['expected_end']) if d.strftime('%Y-%m-%d') not in {p['date'] for p in points}],complete=coverage['missing_days']==0),
                limitations=['Completed UTC daily samples, not exchange OHLC or live quotes.','No stock-account saving for crypto; use the separate crypto workspace.'])


class SampleProvider:
    def catalog(self):
        return [Asset('stock','twelvedata','DEMO','Sample Company','XNYS','USD','America/New_York'),
                Asset('stock','twelvedata','TECH','Sample Technology','XNGS','USD','America/New_York'),
                Asset('etf','twelvedata','FUND','Sample Broad Market Fund','ARCX','USD','America/New_York')]
    def history(self,asset,start,end):
        calendar_now=datetime.fromisoformat(end).replace(hour=23,tzinfo=timezone.utc)
        dates=session_window((datetime.fromisoformat(end)-datetime.fromisoformat(start)).days+1,calendar_now)[2]
        rows=[]
        for day in dates:
            index=(datetime.fromisoformat(day)-datetime(2010,1,1)).days
            price=50+index*.015+math.sin(index/13)*2
            rows.append(dict(date=day,open=price-.4,high=price+1,low=price-1,close=price,volume=100000+(index%17)*2000))
        return rows


class Research:
    def __init__(self,*,sample=True,stocks=None,history=None,now=None):
        self.mode='sample' if sample else 'local-live';self.sample=sample
        self.stocks=stocks or StockService(provider=SampleProvider() if sample else None)
        self.history=history;self.now=now or (lambda:datetime.now(timezone.utc));self.gate=AdmissionGate(2)
    def catalog(self,kind):
        with self.gate.enter():
            if kind=='crypto':return dict(assets=COINS,stale=False,coverage='Three starter coins. Crypto IDs are explicit; no market-wide ranking.')
            result=self.stocks.catalog(self.now());result['assets']=[a for a in result['assets'] if a['asset_class']==kind]
            return result
    def analyze(self,kind,asset_id,days,*,refresh=False):
        with self.gate.enter():
            now=self.now()
            if kind!='crypto':
                result=self.stocks.research(asset_id,days,now,use_cache=True,refresh=refresh)
                if result['asset']['asset_class']!=kind:raise AccountError('asset_mismatch',422)
            else:
                asset=next((a for a in COINS if a['id']==asset_id),None)
                if asset is None:raise AccountError('asset_unavailable',404)
                if days>364:raise AccountError('crypto_window',422)
                if self.sample:
                    dates=pd.date_range(now.date()-timedelta(days=days),periods=days)
                    frame=pd.DataFrame({'price':[100+math.sin(i/9)*4+i*.1 for i in range(days)]},index=dates)
                else:
                    import api
                    frame=(self.history or api.fetch_history)(asset['symbol'],days+1,persist=False)
                result=crypto_result(asset,frame,days,now)
            result['data_mode']=self.mode
            return result


class DisabledResearch:
    mode='not_enabled'
    def catalog(self,*args):raise AccountError('market_not_enabled',503)
    def analyze(self,*args,**kwargs):raise AccountError('market_not_enabled',503)
