"""Managed OIDC authorization-code sign-in; provider tokens never reach the browser."""
from authlib.integrations.starlette_client import OAuth
from account_store import AccountError


class ManagedOIDC:
    def __init__(self,settings,*,transport=None):
        self.issuer=settings.issuer
        oauth=OAuth()
        options={'scope':'openid profile email','code_challenge_method':'S256'}
        if transport is not None:options['transport']=transport
        self.client=oauth.register('identity',client_id=settings.client_id,client_secret=settings.client_secret,
            server_metadata_url=settings.issuer.rstrip('/')+'/.well-known/openid-configuration',
            client_kwargs=options)

    async def begin(self,request,redirect_uri):
        return await self.client.authorize_redirect(request,redirect_uri,prompt='select_account')

    async def complete(self,request):
        token=await self.client.authorize_access_token(request,claims_options={'iss':{'essential':True,'value':self.issuer}})
        # Authlib verifies signed ID-token claims and the stored nonce/state.
        claims=token.get('userinfo')
        if (not token.get('id_token') or not claims or claims.get('iss')!=self.issuer
                or not isinstance(claims.get('sub'),str) or claims.get('email_verified') is not True):
            raise AccountError('invalid_identity',401)
        return dict(issuer=self.issuer,subject=claims['sub'],name=claims.get('name','Research account'))
