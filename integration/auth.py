"""OAuth 2.0 client-credentials + JWT validation for the mock MYOB API.

Two issuers, ONE validation path, so what CI tests is exactly what runs against Auth0:

  AUTH_MODE=local (default)  built-in issuer for offline runs and CI: an RSA key is generated at start-up, POST /oauth/token
                             issues RS256 JWTs (client_credentials), public keys are served at /.well-known/jwks.json.
  AUTH_MODE=auth0            tokens come from Auth0 (https://{AUTH0_DOMAIN}/oauth/token); the API trusts only Auth0's JWKS
                             (https://{AUTH0_DOMAIN}/.well-known/jwks.json). Free Auth0 plan; see docs/AUTH.md.

What every request is checked for (integration/mock_api.py uses `Verifier.verify`):
  * Bearer token present, RS256 only. No "none" or HS256 (prevents algorithm-confusion attacks)
  * signature valid against the issuer's JWKS, key chosen by `kid` (unknown kid -> JWKS refetched once, for key rotation)
  * `iss` = configured issuer, `aud` contains the API identifier, `exp`/`nbf`/`iat` valid (30 s clock-skew leeway)
  * the scope needed for the resource (read:ledger, read:contacts, read:sales)
  * x-myobapi-key header equals the token's client (`azp` / `client_id`), as MYOB ties the API key to the OAuth client
Failures return RFC 6750 errors: 401 invalid_token, 403 insufficient_scope.
"""
from __future__ import annotations

import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

LEEWAY_S = 30
JWKS_TTL_S = 3600
SCOPES = {"GeneralLedger": "read:ledger", "Contact": "read:contacts", "Sale": "read:sales",          # MYOB resources
          "leap": "leap:read", "smokeball": "triconvey:read", "infotrack": "infotrack:read", "trisearch": "trisearch:read", "pexa": "pexa:read"}  # other vendors
ALL_SCOPES = " ".join(SCOPES.values())


def scope_for(resource: str) -> str | None:
    """Scope required for a MYOB resource ('Sale/Invoice/Service') or a vendor route ('leap/v1/matters')."""
    return SCOPES.get(resource.strip("/").split("/")[0])


class AuthError(Exception):
    def __init__(self, status: int, error: str, description: str):
        super().__init__(description)
        self.status, self.error, self.description = status, error, description

    @property
    def www_authenticate(self) -> str:
        return f'Bearer error="{self.error}", error_description="{self.description}"'


@dataclass
class AuthConfig:
    mode: str = "local"                                   # local | auth0
    issuer: str = "http://mock-myob.local/"
    audience: str = "https://myob-mock.dagostino-demo"
    jwks_url: str | None = None                           # auth0 mode: https://{domain}/.well-known/jwks.json

    @classmethod
    def from_env(cls) -> "AuthConfig":
        mode = os.getenv("AUTH_MODE", "local").lower()
        audience = os.getenv("AUTH_AUDIENCE", cls.audience)
        if mode == "auth0":
            domain = os.environ["AUTH0_DOMAIN"].removeprefix("https://").strip("/")
            return cls(mode="auth0", issuer=f"https://{domain}/", audience=audience, jwks_url=f"https://{domain}/.well-known/jwks.json")
        return cls(mode="local", audience=audience)


class LocalIssuer:
    """A tiny OAuth server for offline use: one RSA key pair and a client registry (client_id -> secret, allowed scopes)."""

    def __init__(self, issuer: str, audience: str, clients: dict[str, tuple[str, str]] | None = None, ttl_s: int = 1200):
        self.issuer, self.audience, self.ttl_s = issuer, audience, ttl_s
        self.kid = uuid.uuid4().hex[:16]
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.clients = clients if clients is not None else {"mock-client-id": ("mock-client-secret", ALL_SCOPES)}

    def jwks(self) -> dict:
        jwk = RSAAlgorithm.to_jwk(self._key.public_key(), as_dict=True)
        return {"keys": [{**jwk, "kid": self.kid, "use": "sig", "alg": "RS256"}]}

    def issue(self, client_id: str, scope: str, ttl_s: int | None = None, **overrides) -> str:
        now = int(time.time())
        claims = {"iss": self.issuer, "sub": f"{client_id}@clients", "aud": self.audience, "iat": now,
                  "exp": now + (ttl_s if ttl_s is not None else self.ttl_s), "azp": client_id, "scope": scope,
                  "gty": "client-credentials", "jti": secrets.token_hex(8)}
        claims.update(overrides)
        return jwt.encode(claims, self._key, algorithm="RS256", headers={"kid": self.kid})

    def token_response(self, client_id: str, client_secret: str, audience: str | None, scope: str | None) -> dict:
        """client_credentials grant. Raises AuthError like a real token endpoint would."""
        reg = self.clients.get(client_id)
        if reg is None or not secrets.compare_digest(reg[0], client_secret):
            raise AuthError(401, "invalid_client", "Unknown client or wrong secret")
        if audience not in (None, "", self.audience):
            raise AuthError(403, "access_denied", "Client is not authorised for this audience")
        allowed = set(reg[1].split())
        granted = allowed if not scope else set(scope.split()) & allowed
        tok = self.issue(client_id, " ".join(sorted(granted)))
        return {"access_token": tok, "token_type": "Bearer", "expires_in": self.ttl_s, "scope": " ".join(sorted(granted))}


@dataclass
class JWKSCache:
    """Caches the issuer's signing keys; refetches when stale or when a token names an unknown kid (key rotation)."""
    fetch: Callable[[], dict]
    ttl_s: int = JWKS_TTL_S
    _keys: dict = field(default_factory=dict)
    _at: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _load(self) -> None:
        jwks = self.fetch()
        self._keys = {k["kid"]: RSAAlgorithm.from_jwk(k) for k in jwks.get("keys", []) if k.get("kty") == "RSA" and "kid" in k}
        self._at = time.time()

    def key(self, kid: str):
        with self._lock:
            if not self._keys or time.time() - self._at > self.ttl_s:
                self._load()
            if kid not in self._keys:                          # maybe the issuer rotated keys: refetch once
                self._load()
            if kid not in self._keys:
                raise AuthError(401, "invalid_token", "Signing key not found")
            return self._keys[kid]


def http_jwks_fetcher(url: str) -> Callable[[], dict]:
    def fetch() -> dict:
        import requests
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    return fetch


class Verifier:
    def __init__(self, cfg: AuthConfig, jwks: JWKSCache):
        self.cfg, self.jwks = cfg, jwks

    def verify(self, authorization: str | None, api_key: str | None, required_scope: str | None, require_key: bool = True) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise AuthError(401, "invalid_request", "Missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise AuthError(401, "invalid_token", "Malformed token")
        if header.get("alg") != "RS256":
            raise AuthError(401, "invalid_token", "Only RS256 tokens are accepted")
        key = self.jwks.key(header.get("kid", ""))
        try:
            claims = jwt.decode(token, key, algorithms=["RS256"], audience=self.cfg.audience, issuer=self.cfg.issuer,
                                leeway=LEEWAY_S, options={"require": ["exp", "iat", "iss", "aud"]})
        except jwt.ExpiredSignatureError:
            raise AuthError(401, "invalid_token", "Token expired")
        except jwt.InvalidAudienceError:
            raise AuthError(401, "invalid_token", "Wrong audience")
        except jwt.InvalidIssuerError:
            raise AuthError(401, "invalid_token", "Wrong issuer")
        except jwt.PyJWTError:
            raise AuthError(401, "invalid_token", "Invalid token")
        client = claims.get("azp") or claims.get("client_id")
        if require_key and (not api_key or api_key != client):          # MYOB (x-myobapi-key) and Smokeball (x-api-key) tie keys to clients
            raise AuthError(403, "invalid_client", "API key header does not match the token's client")
        if required_scope and required_scope not in str(claims.get("scope", "")).split():
            raise AuthError(403, "insufficient_scope", f"Requires scope {required_scope}")
        return claims


def build(cfg: AuthConfig | None = None, jwks_fetch: Callable[[], dict] | None = None) -> tuple[AuthConfig, Verifier, LocalIssuer | None]:
    """Wire config -> (verifier, local issuer or None). `jwks_fetch` lets tests stand in for Auth0."""
    cfg = cfg or AuthConfig.from_env()
    issuer = None
    if cfg.mode == "local":
        issuer = LocalIssuer(cfg.issuer, cfg.audience)
        fetch = jwks_fetch or issuer.jwks
    else:
        fetch = jwks_fetch or http_jwks_fetcher(cfg.jwks_url)
    return cfg, Verifier(cfg, JWKSCache(fetch)), issuer
