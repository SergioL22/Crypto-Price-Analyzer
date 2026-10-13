"""User-owned account records, opaque sessions and revision-bound import previews."""
from contextlib import contextmanager
import hashlib
import json
import secrets
import time
from sqlalchemy import (create_engine,MetaData,Table,Column,String,Integer,Float,Text,
                        ForeignKey,UniqueConstraint,select,update,delete,event)
from sqlalchemy.exc import IntegrityError
from account_models import Workspace


class AccountError(Exception):
    def __init__(self,code,status=409):self.code=code;self.status=status


def hash_token(token):return hashlib.sha256(token.encode()).hexdigest()
def empty():return Workspace(version=1).model_dump()


class AccountStore:
    def __init__(self,url,*,clock=time.time):
        self.clock=clock
        self.engine=create_engine(url,connect_args={'check_same_thread':False,'timeout':15} if url.startswith('sqlite') else {},pool_pre_ping=True)
        if self.engine.dialect.name=='sqlite':
            @event.listens_for(self.engine,'connect')
            def foreign_keys(connection,_):connection.execute('PRAGMA foreign_keys=ON')
        metadata=MetaData()
        self.accounts=Table('accounts',metadata,Column('id',String(64),primary_key=True),Column('issuer',String(500),nullable=False),Column('subject',String(255),nullable=False),Column('name',String(200),nullable=False),UniqueConstraint('issuer','subject'))
        self.sessions=Table('account_sessions',metadata,Column('token_hash',String(64),primary_key=True),Column('owner',String(64),ForeignKey('accounts.id',ondelete='CASCADE'),nullable=False),Column('csrf',String(64),nullable=False),Column('expires',Float,nullable=False))
        self.workspaces=Table('account_workspaces',metadata,Column('owner',String(64),ForeignKey('accounts.id',ondelete='CASCADE'),primary_key=True),Column('revision',Integer,nullable=False),Column('payload',Text,nullable=False))
        self.previews=Table('account_import_previews',metadata,Column('token_hash',String(64),primary_key=True),Column('owner',String(64),ForeignKey('accounts.id',ondelete='CASCADE'),nullable=False),Column('session_hash',String(64),ForeignKey('account_sessions.token_hash',ondelete='CASCADE'),nullable=False),Column('revision',Integer,nullable=False),Column('expires',Float,nullable=False),Column('payload',Text,nullable=False))
        self.attempts=Table('account_login_attempts',metadata,Column('key',String(64),primary_key=True),Column('window',Integer,nullable=False),Column('count',Integer,nullable=False))
        metadata.create_all(self.engine)

    @contextmanager
    def write(self):
        with self.engine.connect() as db:
            if self.engine.dialect.name=='sqlite':db.exec_driver_sql('BEGIN IMMEDIATE')
            else:db.begin()
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    def login(self,issuer,subject,name):
        if not isinstance(subject,str) or not 1<=len(subject)<=255:raise AccountError('invalid_identity',401)
        name=str(name or 'Research account')[:200]
        try:
            with self.write() as db:
                account=db.execute(select(self.accounts).where(self.accounts.c.issuer==issuer,self.accounts.c.subject==subject)).mappings().first()
                if account is None:
                    owner=secrets.token_hex(16)
                    db.execute(self.accounts.insert().values(id=owner,issuer=issuer,subject=subject,name=name))
                    db.execute(self.workspaces.insert().values(owner=owner,revision=0,payload=json.dumps(empty())))
                else:owner=account['id']
        except IntegrityError:
            with self.engine.connect() as db:
                owner=db.execute(select(self.accounts.c.id).where(self.accounts.c.issuer==issuer,self.accounts.c.subject==subject)).scalar_one()
        token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        with self.write() as db:
            db.execute(delete(self.sessions).where(self.sessions.c.expires<=self.clock()))
            db.execute(self.sessions.insert().values(token_hash=hash_token(token),owner=owner,csrf=csrf,expires=self.clock()+8*3600))
        return token

    def session(self,token):
        if not token or not isinstance(token,str) or len(token)>128:raise AccountError('sign_in_required',401)
        with self.engine.connect() as db:
            row=db.execute(select(self.sessions,self.accounts.c.name).join(self.accounts,self.sessions.c.owner==self.accounts.c.id).where(self.sessions.c.token_hash==hash_token(token),self.sessions.c.expires>self.clock())).mappings().first()
        if row is None:raise AccountError('sign_in_required',401)
        return dict(row)

    def logout(self,session):
        with self.write() as db:db.execute(delete(self.sessions).where(self.sessions.c.token_hash==session['token_hash']))

    def read(self,owner):
        with self.engine.connect() as db:row=db.execute(select(self.workspaces).where(self.workspaces.c.owner==owner)).mappings().one()
        return dict(revision=row['revision'],workspace=json.loads(row['payload']))

    def save(self,owner,revision,workspace):
        payload=Workspace.model_validate(workspace).model_dump()
        with self.write() as db:
            result=db.execute(update(self.workspaces).where(self.workspaces.c.owner==owner,self.workspaces.c.revision==revision).values(revision=revision+1,payload=json.dumps(payload,allow_nan=False)))
            if result.rowcount!=1:raise AccountError('workspace_changed')
        return dict(revision=revision+1,workspace=payload)

    def preview(self,session,workspace):
        payload=Workspace.model_validate(workspace).model_dump()
        current=self.read(session['owner'])
        token=secrets.token_urlsafe(32)
        with self.write() as db:
            db.execute(delete(self.previews).where(self.previews.c.expires<=self.clock()))
            db.execute(delete(self.previews).where(self.previews.c.session_hash==session['token_hash']))
            db.execute(self.previews.insert().values(token_hash=hash_token(token),owner=session['owner'],session_hash=session['token_hash'],revision=current['revision'],expires=self.clock()+600,payload=json.dumps(payload)))
        return dict(token=token,destination=dict(account_id=session['owner'],name=session['name']),revision=current['revision'],expires_in_seconds=600,
                    incoming={k:len(payload[k]) for k in ('listings','holdings','alerts')},existing={k:len(current['workspace'][k]) for k in ('listings','holdings','alerts')},workspace=payload)

    def confirm(self,session,token):
        with self.write() as db:
            preview=db.execute(select(self.previews).where(self.previews.c.token_hash==hash_token(token),self.previews.c.owner==session['owner'],self.previews.c.session_hash==session['token_hash'],self.previews.c.expires>self.clock())).mappings().first()
            if preview is None:raise AccountError('preview_unavailable',404)
            changed=db.execute(update(self.workspaces).where(self.workspaces.c.owner==session['owner'],self.workspaces.c.revision==preview['revision']).values(revision=preview['revision']+1,payload=preview['payload']))
            if changed.rowcount!=1:raise AccountError('workspace_changed')
            consumed=db.execute(delete(self.previews).where(self.previews.c.token_hash==hash_token(token)))
            if consumed.rowcount!=1:raise AccountError('preview_unavailable',409)
            return dict(revision=preview['revision']+1,workspace=json.loads(preview['payload']))

    def cancel_preview(self,session):
        with self.write() as db:
            db.execute(delete(self.previews).where(self.previews.c.owner==session['owner'],self.previews.c.session_hash==session['token_hash']))

    def throttle(self,key,maximum=10):
        """Atomic fixed-minute counter shared by account-app workers."""
        key=hash_token(key);window=int(self.clock()//60)
        try:
            with self.write() as db:
                db.execute(delete(self.attempts).where(self.attempts.c.window<window-60))
                row=db.execute(select(self.attempts).where(self.attempts.c.key==key)).mappings().first()
                if row is None:db.execute(self.attempts.insert().values(key=key,window=window,count=1));return
                if row['window']!=window:
                    changed=db.execute(update(self.attempts).where(self.attempts.c.key==key,self.attempts.c.window==row['window']).values(window=window,count=1))
                    if changed.rowcount==1:return
                changed=db.execute(update(self.attempts).where(self.attempts.c.key==key,self.attempts.c.window==window,self.attempts.c.count<maximum).values(count=self.attempts.c.count+1))
                if changed.rowcount!=1:raise AccountError('rate_limited',429)
        except IntegrityError:raise AccountError('rate_limited',429) from None
