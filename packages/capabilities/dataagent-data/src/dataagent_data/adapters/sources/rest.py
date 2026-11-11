"""Allowlisted HTTP GET only, bounded JSON responses, no implicit redirects."""
import base64
import json
from urllib.error import HTTPError
from urllib.parse import urlsplit, parse_qsl
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request
from .base import ReadOnlySource


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def origin(url):
    parsed=urlsplit(url)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise ValueError('REST URL requires HTTP(S) origin without userinfo or fragment')
    if any(k.lower().replace('-','_') in {'token','access_token','password','secret','api_key','apikey','authorization'} for k,v in parse_qsl(parsed.query)):
        raise ValueError('REST credentials must use host-injected headers')
    return (parsed.scheme,parsed.hostname.lower(),parsed.port or (443 if parsed.scheme=='https' else 80))


def approved(url, allowed):
    if origin(url) not in allowed: raise PermissionError('REST origin is not in host configured allowlist')


def auth_headers(credentials):
    if not credentials: return {}
    auth=credentials.get('auth')
    if auth=='bearer' and set(credentials)<={'auth','token'} and isinstance(credentials.get('token'),str):
        token=credentials['token']
        if '\r' in token or '\n' in token: raise ValueError('invalid authentication header')
        return {'Authorization':'Bearer '+token}
    if auth=='basic' and set(credentials)<={'auth','user','password'} and all(isinstance(credentials.get(k),str) for k in ['user','password']):
        encoded=base64.b64encode((credentials['user']+':'+credentials['password']).encode()).decode()
        return {'Authorization':'Basic '+encoded}
    raise ValueError('unsupported REST authentication; use host-bound bearer or basic credentials')


def fetch(url, headers, timeout=5):
    # No environment proxy can silently route host-authorized requests elsewhere.
    opener=build_opener(ProxyHandler({}),NoRedirect())
    try:
        response=opener.open(Request(url,headers={'Accept':'application/json',**headers},method='GET'),timeout=timeout)
    except HTTPError as exc:
        status=exc.code;retry=exc.headers.get('Retry-After');exc.close()
        return status,None,{'retry_after':retry}
    with response:
        content_type=response.headers.get_content_type()
        if content_type!='application/json' and not content_type.endswith('+json'):
            return response.status,None,{'error':'unsupported_content_type'}
        body=response.read(4*1024*1024+1)
        if len(body)>4*1024*1024: return response.status,None,{'error':'response_too_large'}
        # Keep allowlisted response metadata; cookies and authorization never enter profiles.
        metadata={'etag':response.headers.get('ETag'),'last_modified':response.headers.get('Last-Modified'),
            'source_version':response.headers.get('X-Source-Version')}
        try: payload=json.loads(body)
        except (UnicodeError,ValueError): return response.status,None,{'error':'invalid_json'}
        return response.status,payload,metadata


class RESTSource(ReadOnlySource):
    def describe(self, ctx):
        # REST has no universal schema endpoint: the description is a bounded sample.
        return self.read(ctx,budget_rows=1)

    def read(self, ctx, *, budget_rows=200):
        from ...observation.http import probe_rest
        return probe_rest(self.selection,ctx,workspace=self.workspace,budget_rows=budget_rows,
            credentials=self.credentials,allowed_origins=self.allowed_origins)
