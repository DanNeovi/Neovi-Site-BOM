"""Google sign-in and short-lived sessions for the loopback SiteBOM server."""

import os
import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SETTINGS = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Neovi' / 'SiteBOM'
CLIENT_ID_FILE = SETTINGS / 'google-client-id.txt'
CLIENT_SECRET_FILE = SETTINGS / 'google-client-secret.txt'
ALLOWED_EMAILS_FILE = SETTINGS / 'allowed-emails.txt'
SESSION_COOKIE = 'sitebom_session'
OAUTH_COOKIE = 'sitebom_oauth'
SESSION_SECONDS = 12 * 60 * 60
_sessions = {}
_pending = {}
_lock = threading.Lock()


def client_id():
    value = os.environ.get('SITEBOM_GOOGLE_CLIENT_ID', '').strip()
    if not value and CLIENT_ID_FILE.is_file():
        value = CLIENT_ID_FILE.read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com', value):
        return ''
    return value


def allowed_emails():
    value = os.environ.get('SITEBOM_ALLOWED_EMAILS', '').strip()
    if not value and ALLOWED_EMAILS_FILE.is_file():
        value = ALLOWED_EMAILS_FILE.read_text(encoding='utf-8')
    return {email.strip().lower() for email in (value or 'danielb@neovi.co').replace(',', '\n').splitlines()
            if email.strip()}


def client_secret():
    return CLIENT_SECRET_FILE.read_text(encoding='utf-8').strip() if CLIENT_SECRET_FILE.is_file() else ''


def start_google_login(redirect_uri):
    audience = client_id()
    if not audience or not client_secret():
        raise ValueError('Google sign-in is not configured')
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    nonce = secrets.token_urlsafe(24)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    with _lock:
        _pending[state] = {'verifier': verifier, 'nonce': nonce, 'expires': time.time() + 600}
    query = urlencode({'client_id': audience, 'redirect_uri': redirect_uri,
                       'response_type': 'code', 'scope': 'openid email profile',
                       'state': state, 'nonce': nonce, 'code_challenge': challenge,
                       'code_challenge_method': 'S256', 'prompt': 'select_account',
                       'hd': 'neovi.co'})
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + query, state


def consume_google_state(cookie_header, state):
    cookie = cookie_value(cookie_header, OAUTH_COOKIE)
    if not state or not cookie or not hmac.compare_digest(state, cookie):
        raise ValueError('Invalid Google sign-in state')
    with _lock:
        pending = _pending.pop(state, None)
    if not pending or pending['expires'] <= time.time():
        raise ValueError('Google sign-in expired; start again')
    return pending


def exchange_google_code(code, verifier, redirect_uri):
    body = urlencode({'code': code, 'client_id': client_id(), 'client_secret': client_secret(),
                      'redirect_uri': redirect_uri, 'grant_type': 'authorization_code',
                      'code_verifier': verifier}).encode()
    request = Request('https://oauth2.googleapis.com/token', data=body,
                      headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
    with urlopen(request, timeout=15) as response:
        token = json.load(response)
    if not token.get('id_token'):
        raise ValueError('Google did not return an ID token')
    return token['id_token']


def verify_google_credential(credential, nonce):
    """Verify signature, audience, expiry, and Workspace identity server-side."""
    from google.auth.transport import requests
    from google.oauth2 import id_token

    audience = client_id()
    if not audience:
        raise ValueError('Google sign-in is not configured')
    claims = id_token.verify_oauth2_token(credential, requests.Request(), audience,
                                         clock_skew_in_seconds=30)
    email = str(claims.get('email', '')).lower()
    if (claims.get('email_verified') not in (True, 'true') or
            claims.get('hd') != 'neovi.co' or email not in allowed_emails() or
            not hmac.compare_digest(str(claims.get('nonce', '')), nonce) or
            not claims.get('sub')):
        raise ValueError('This Google account is not allowed to use SiteBOM')
    return {'sub': claims['sub'], 'email': email}


def cookie_value(header, name):
    for segment in (header or '').split(';'):
        key, separator, value = segment.strip().partition('=')
        if separator and key == name and re.fullmatch(r'[A-Za-z0-9_-]+', value):
            return value
    return ''


def create_session(user):
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = {'user': user, 'expires': time.time() + SESSION_SECONDS}
    return token


def session_user(header):
    token = cookie_value(header, SESSION_COOKIE)
    with _lock:
        session = _sessions.get(token)
        if session and session['expires'] > time.time():
            return session['user']
        _sessions.pop(token, None)
    return None


def revoke_session(header):
    token = cookie_value(header, SESSION_COOKIE)
    with _lock:
        _sessions.pop(token, None)


def session_header(token):
    return f'{SESSION_COOKIE}={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_SECONDS}'


def expired_session_header():
    return f'{SESSION_COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'


def oauth_cookie_header(state):
    return f'{OAUTH_COOKIE}={state}; HttpOnly; SameSite=Lax; Path=/auth; Max-Age=600'
