import base64
import hashlib
import json
import time
from urllib.parse import parse_qs,urlsplit
import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes
from fastapi.testclient import TestClient
from account_auth import ManagedOIDC
from account_backend import create_app
from account_settings import AccountSettings
from account_store import AccountStore


def b64(value):return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


@pytest.mark.parametrize('invalid',[None,'nonce','issuer','audience','expired','signature','state','missing_id_token','unverified_email'])
def test_managed_oidc_checks_signed_identity_state_nonce_audience_and_expiry(tmp_path,invalid):
    issuer='https://identity.example/'
    settings=AccountSettings('https://research.example','sqlite:///'+(tmp_path/'accounts.db').as_posix(),'test-state-secret-at-least-32-characters',issuer,'client-test','secret-test')
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    numbers=private.public_key().public_numbers()
    public=dict(kty='RSA',kid='fixture-key',use='sig',alg='RS256',n=b64(numbers.n.to_bytes((numbers.n.bit_length()+7)//8,'big')),e=b64(numbers.e.to_bytes((numbers.e.bit_length()+7)//8,'big')))
    observed={}
    def transport(request):
        if request.url.path=='/.well-known/openid-configuration':
            return httpx.Response(200,json=dict(issuer=issuer,authorization_endpoint=issuer+'authorize',token_endpoint=issuer+'token',jwks_uri=issuer+'jwks',response_types_supported=['code'],id_token_signing_alg_values_supported=['RS256']))
        if request.url.path=='/jwks':return httpx.Response(200,json={'keys':[public]})
        if request.url.path=='/token':
            form=parse_qs(request.content.decode())
            assert b64(hashlib.sha256(form['code_verifier'][0].encode()).digest())==observed['code_challenge']
            claims=dict(iss=issuer,sub='verified-subject',aud='client-test',iat=int(time.time()),exp=int(time.time())+600,nonce=observed['nonce'],name='<img src=x>',email_verified=True)
            if invalid=='nonce':claims['nonce']='wrong'
            if invalid=='issuer':claims['iss']='https://other.example/'
            if invalid=='audience':claims['aud']='other-client'
            if invalid=='expired':claims['exp']=int(time.time())-600
            if invalid=='unverified_email':claims['email_verified']=False
            body=b64(json.dumps({'alg':'RS256','kid':'fixture-key','typ':'JWT'}).encode())+'.'+b64(json.dumps(claims).encode())
            signature=private.sign(body.encode(),padding.PKCS1v15(),hashes.SHA256())
            if invalid=='signature':signature=bytes(len(signature))
            token=dict(access_token='synthetic-access-token',token_type='Bearer',expires_in=600,id_token=body+'.'+b64(signature))
            if invalid=='missing_id_token':token.pop('id_token');token['userinfo']=claims
            return httpx.Response(200,json=token)
        raise AssertionError('Unmocked identity-provider request')
    store=AccountStore(settings.database_url)
    identity=ManagedOIDC(settings,transport=httpx.MockTransport(transport))
    app=create_app(settings,store,identity)
    c=TestClient(app,base_url=settings.origin)
    response=c.get('/auth/login',follow_redirects=False)
    assert response.status_code==302
    params=parse_qs(urlsplit(response.headers['location']).query)
    observed.update({k:v[0] for k,v in params.items()})
    assert observed['code_challenge_method']=='S256' and observed['redirect_uri']==settings.origin+'/auth/callback'
    state='wrong-state' if invalid=='state' else observed['state']
    callback=c.get('/auth/callback',params={'code':'synthetic-code','state':state},follow_redirects=False)
    if invalid:
        assert callback.status_code==401
        assert c.get('/v2/session').status_code==401
    else:
        assert callback.status_code==303
        cookie=callback.headers['set-cookie']
        assert '__Host-research-session=' in cookie and 'Secure' in cookie and 'HttpOnly' in cookie
        assert c.get('/v2/session').json()['name']=='<img src=x>'
        assert c.post('/auth/demo',json={'profile':'avery'},headers={'Origin':settings.origin}).status_code==404
        assert c.get('/v2/session',headers={'Host':'evil.example'}).status_code==403
    store.engine.dispose()
