"""Snapshot-bound educational assessments, separate from predictive validation."""
import os
import secrets
from datetime import timedelta
import pandas as pd
from itsdangerous import URLSafeTimedSerializer,BadSignature
import analysis
from llm import OpenAIRecommender,INSTRUCTIONS
from recommendations import RecommendationError,validate_recommendation
from account_store import AccountError
from stock_service import session_window


def provider():
    instructions=INSTRUCTIONS.replace('educational crypto','educational stock, ETF or crypto')+"""
No fundamental, news or valuation evidence was supplied. Do not infer it from the asset name.
Prediction validation is separate and is not supplied as a buy/sell signal. Never claim
a price target, forecast accuracy or probability of success. Backtest execution uses the
same daily closing observation as its signal: illustrative and optimistic, not tradable proof.
"""
    return OpenAIRecommender(os.environ.get('OPENAI_API_KEY'),os.environ.get('OPENAI_MODEL'),instructions=instructions)


def evidence(data):
    if not data['window']['complete'] or data['indicators'] is None:raise AccountError('assessment_history',422)
    points=data['history'];first,last=points[0],points[-1]
    frame=pd.DataFrame({'price':[p['price'] for p in points]},index=pd.to_datetime([p['date'] for p in points]))
    backtest=analysis.backtest_dataframe(frame,data['asset']['symbol'],days=len(points))
    closed=backtest['total_trades']
    return dict(asset=data['asset'],data_mode=data['data_mode'],
                history=dict(start=first['date'],end=last['date'],observations=len(points),latest_price_usd=last['price'],
                             window_change_pct=(last['price']/first['price']-1)*100),
                indicators=data['indicators'],backtest=dict(strategy='RSI / moving average, illustrative same-close execution',
                closed_trades=closed,win_rate_pct=backtest['win_rate'] if closed else None,
                average_closed_return_pct=backtest['avg_return'] if closed else None,asset_drawdown_pct=backtest['max_drawdown']),
                position=dict(included=False),limitations=data['limitations']+[
                    'No fundamentals, news, valuation, risk tolerance or investment horizon were supplied.',
                    'Backtest excludes fees, slippage and dividends; signals and fills share a close, so results are optimistic.',
                    'Historical indicators are correlated descriptions, not a validated forecast.',
                    'AI confidence is qualitative evidence judgment, not measured accuracy or probability of profit.'])


class Assessments:
    def __init__(self,secret,*,factory=None):
        self.serializer=URLSafeTimedSerializer(secret,salt='research-assessment-v1');self.factory=factory or provider

    def bind(self,data,session):
        if not data['window']['complete'] or data['indicators'] is None:return None
        return self.serializer.dumps(dict(session=session['token_hash'],nonce=secrets.token_hex(16),evidence=evidence(data)))

    def read(self,token,session,now):
        try:value=self.serializer.loads(token,max_age=600)
        except BadSignature:raise AccountError('assessment_expired',409) from None
        if value['session']!=session['token_hash']:raise AccountError('assessment_expired',409)
        data=value['evidence'];asset=data['asset']
        latest=(now.date()-timedelta(days=1)).isoformat() if asset['asset_class']=='crypto' else session_window(35,now)[2][-1]
        if data['history']['end']!=latest:raise AccountError('assessment_expired',409)
        return data

    def recommend(self,data,position=None):
        if position is not None:data['position']=dict(included=True,quantity=position['quantity'],average_cost_usd=position['cost'])
        if data['data_mode']=='sample':
            result=dict(action='HOLD',confidence='low',summary='Sample illustration only: these synthetic prices cannot support a real investment decision.',
                        confidence_explanation='This is an offline example, not an OpenAI response or a prediction.',
                        reasons=[dict(evidence_keys=['history.latest_price_usd'],explanation='Inspect the latest synthetic historical price alongside the chart.')],
                        risks=[dict(evidence_keys=['limitations'],explanation='Historical signals and the illustrative backtest cannot establish future accuracy.')])
            source='offline-sample'
        else:result=validate_recommendation(self.factory().recommend(data),data);source='openai'
        return dict(source=source,recommendation=result,evidence=data,prediction=dict(promoted=False,calibrated=False,accuracy=None))
