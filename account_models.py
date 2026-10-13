"""Validated account workspace and explicit migration contracts."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

AssetId=Annotated[str,Field(strict=True,pattern=r'^twelvedata:(stock|etf):(XNYS|XNAS|XNGS|XNMS|XNCM|ARCX|XASE|BATS):USD:[A-Za-z0-9.^_-]{1,100}$')]
Number=Annotated[float,Field(strict=True,allow_inf_nan=False,ge=0)]


class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)


class Listing(Contract):
    id:AssetId
    name:Annotated[str,Field(strict=True,min_length=1,max_length=500)]


class Holding(Contract):
    id:AssetId
    quantity:Annotated[float,Field(strict=True,allow_inf_nan=False,gt=0)]
    cost:Number


class Alert(Contract):
    id:AssetId
    type:Literal['price','rsi']
    direction:Literal['above','below']
    threshold:Number
    triggered:Annotated[bool,Field(strict=True)]=False

    @model_validator(mode='after')
    def rsi_range(self):
        if self.type=='rsi' and self.threshold>100:raise ValueError('RSI exceeds 100')
        return self


class Workspace(Contract):
    version:Literal[1]
    listings:list[Listing]=Field(default_factory=list,max_length=50)
    holdings:list[Holding]=Field(default_factory=list,max_length=50)
    alerts:list[Alert]=Field(default_factory=list,max_length=50)

    @model_validator(mode='before')
    @classmethod
    def exact_version(cls,data):
        if isinstance(data,dict) and 'version' in data and type(data['version']) is not int:raise ValueError('Integer version required')
        return data

    @model_validator(mode='after')
    def unique_ids(self):
        for rows in (self.listings,self.holdings):
            if len({r.id for r in rows})!=len(rows):raise ValueError('Duplicate asset')
        return self


class WorkspaceUpdate(Contract):
    revision:Annotated[int,Field(strict=True,ge=0)]
    workspace:Workspace


class ImportConfirm(Contract):
    token:Annotated[str,Field(strict=True,min_length=40,max_length=128)]
    confirm:Literal[True]

    @model_validator(mode='before')
    @classmethod
    def explicit_confirmation(cls,data):
        if isinstance(data,dict) and data.get('confirm') is not True:raise ValueError('Confirmation required')
        return data


class DemoLogin(Contract):
    profile:Literal['avery','sam']
