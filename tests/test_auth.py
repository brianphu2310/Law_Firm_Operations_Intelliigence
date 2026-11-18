"""OAuth 2.0 / JWT protection of the mock MYOB API (integration/auth.py).

Every attack here is rejected by the same Verifier that runs in AUTH_MODE=auth0; the Auth0 test stands a local issuer in for
Auth0's token endpoint and JWKS (CI has no network access to Auth0).
"""
import base64
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
jwt = pytest.importorskip("jwt")
from fastapi.testclient import TestClient  # noqa: E402

from integration import auth as A  # noqa: E402
from integration import extract_load as el  # noqa: E402
from integration.mock_api import create_app  # noqa: E402

CID = "mock-client-id"
INVOICES = "Sale/Invoice/Service"


@pytest.fixture()
def api():
    return TestClient(create_app())


def _cf(api, tok):
    return api.get("/accountright/", headers=_h(tok)).json()[0]["Id"]


def _h(tok, key=CID):
    return {"Authorization": f"Bearer {tok}", "x-myobapi-key": key, "x-myobapi-version": "v2"}


def _get(api, tok, resource=INVOICES, key=CID):
    cf = "d4a6b1e2-0c5f-4f3e-9a71-5b2c8e6f1a90"
    return api.get(f"/accountright/{cf}/{resource}", headers=_h(tok, key), params={"$top": 1})


def _issuer(api) -> A.LocalIssuer:
    return api.app.state.issuer


# ------------------------------------------------------------- happy path --
def test_token_endpoint_issues_rs256_jwt_with_scopes(api):
    r = api.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": CID, "client_secret": "mock-client-secret",
                                       "audience": "https://myob-mock.dagostino-demo"})
    assert r.status_code == 200
    tok = r.json()["access_token"]
    assert jwt.get_unverified_header(tok)["alg"] == "RS256"
    claims = jwt.decode(tok, options={"verify_signature": False})
    assert claims["azp"] == CID and set(claims["scope"].split()) == {"read:ledger", "read:contacts", "read:sales"}
    assert _get(api, tok).status_code == 200


def test_jwks_endpoint_publishes_only_public_key(api):
    keys = api.get("/.well-known/jwks.json").json()["keys"]
    assert len(keys) == 1 and keys[0]["kty"] == "RSA" and keys[0]["alg"] == "RS256"
    assert "d" not in keys[0] and "p" not in keys[0]                     # no private-key material


def test_wrong_client_secret_is_rejected(api):
    r = api.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": CID, "client_secret": "guess"})
    assert r.status_code == 401 and r.json()["error"] == "invalid_client"


# ------------------------------------------------------------ token attacks --
def test_missing_or_garbage_token_is_401_with_rfc6750_header(api):
    r = api.get("/accountright/", headers={"x-myobapi-key": CID, "x-myobapi-version": "v2"})
    assert r.status_code == 401 and r.headers["WWW-Authenticate"].startswith("Bearer error=")
    assert _get(api, "not.a.jwt").status_code == 401


def test_token_signed_by_another_key_is_rejected(api):
    impostor = A.LocalIssuer(_issuer(api).issuer, _issuer(api).audience)
    impostor.kid = _issuer(api).kid                                       # same kid, different key: signature must fail
    r = _get(api, impostor.issue(CID, A.ALL_SCOPES))
    assert r.status_code == 401 and r.json()["error"] == "invalid_token"


def test_alg_none_and_hs256_confusion_are_rejected(api):
    claims = jwt.decode(_issuer(api).issue(CID, A.ALL_SCOPES), options={"verify_signature": False})
    b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    none_tok = f"{b64({'alg': 'none', 'kid': _issuer(api).kid})}.{b64(claims)}."
    assert _get(api, none_tok).status_code == 401
    import hashlib
    import hmac
    secret = json.dumps(_issuer(api).jwks()).encode()                     # attacker uses the public JWKS as an HMAC secret
    signing_input = f"{b64({'alg': 'HS256', 'typ': 'JWT', 'kid': _issuer(api).kid})}.{b64(claims)}"
    sig = base64.urlsafe_b64encode(hmac.new(secret, signing_input.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    r = _get(api, f"{signing_input}.{sig}")
    assert r.status_code == 401 and r.json()["error_description"] == "Only RS256 tokens are accepted"


@pytest.mark.parametrize("override,error", [({"aud": "https://some-other-api"}, "Wrong audience"),
                                            ({"iss": "https://evil.example/"}, "Wrong issuer")])
def test_wrong_audience_or_issuer_is_rejected(api, override, error):
    r = _get(api, _issuer(api).issue(CID, A.ALL_SCOPES, **override))
    assert r.status_code == 401 and r.json()["error_description"] == error


def test_expired_token_is_rejected_but_clock_skew_is_tolerated(api):
    now = int(time.time())
    expired = _issuer(api).issue(CID, A.ALL_SCOPES, iat=now - 3600, exp=now - A.LEEWAY_S - 5)
    assert _get(api, expired).json()["error_description"] == "Token expired"
    just_expired = _issuer(api).issue(CID, A.ALL_SCOPES, iat=now - 3600, exp=now - 5)    # within the 30 s leeway
    assert _get(api, just_expired).status_code == 200


# ----------------------------------------------------------- authorisation --
@pytest.mark.parametrize("resource,needed", [("Sale/Invoice/Service", "read:sales"), ("Contact/Customer", "read:contacts"),
                                             ("GeneralLedger/Account", "read:ledger")])
def test_each_resource_needs_its_own_scope(api, resource, needed):
    others = " ".join(s for s in A.ALL_SCOPES.split() if s != needed)
    r = _get(api, _issuer(api).issue(CID, others), resource)
    assert r.status_code == 403 and r.json()["error"] == "insufficient_scope"
    assert _get(api, _issuer(api).issue(CID, needed), resource).status_code == 200


def test_token_endpoint_only_grants_scopes_the_client_is_allowed(api):
    _issuer(api).clients["reporting-only"] = ("s3cret", "read:sales")
    r = api.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": "reporting-only", "client_secret": "s3cret",
                                       "scope": "read:sales read:ledger"})
    assert r.json()["scope"] == "read:sales"


def test_api_key_header_must_match_the_tokens_client(api):
    r = _get(api, _issuer(api).issue(CID, A.ALL_SCOPES), key="someone-elses-key")
    assert r.status_code == 403 and r.json()["error"] == "invalid_client"


# ------------------------------------------------------------- key rotation --
def test_jwks_cache_refetches_once_on_unknown_kid():
    old, new = A.LocalIssuer("i", "a"), A.LocalIssuer("i", "a")
    served = {"jwks": old.jwks()}
    calls = []
    cache = A.JWKSCache(fetch=lambda: (calls.append(1), served["jwks"])[1])
    cache.key(old.kid)
    served["jwks"] = new.jwks()                                           # issuer rotates its signing key
    cache.key(new.kid)
    assert len(calls) == 2
    with pytest.raises(A.AuthError):
        cache.key("never-published")


# ------------------------------------------------------------ Auth0 wiring --
def test_auth0_mode_trusts_only_the_auth0_issuer():
    fake_auth0 = A.LocalIssuer("https://dev-example.us.auth0.com/", "https://myob-mock.dagostino-demo")
    cfg = A.AuthConfig(mode="auth0", issuer="https://dev-example.us.auth0.com/", audience="https://myob-mock.dagostino-demo",
                       jwks_url="https://dev-example.us.auth0.com/.well-known/jwks.json")
    api = TestClient(create_app(cfg, jwks_fetch=fake_auth0.jwks))
    assert api.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": CID, "client_secret": "x"}).status_code == 404
    assert api.get("/.well-known/jwks.json").status_code == 404
    assert _get(api, fake_auth0.issue(CID, A.ALL_SCOPES)).status_code == 200
    local = A.LocalIssuer("http://mock-myob.local/", "https://myob-mock.dagostino-demo")
    assert _get(api, local.issue(CID, A.ALL_SCOPES)).status_code == 401  # a token from any other issuer is refused


def test_auth_config_from_env(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "auth0")
    monkeypatch.setenv("AUTH0_DOMAIN", "https://dev-z1apvxcaj6hhb84a.us.auth0.com/")
    cfg = A.AuthConfig.from_env()
    assert cfg.issuer == "https://dev-z1apvxcaj6hhb84a.us.auth0.com/"
    assert cfg.jwks_url == "https://dev-z1apvxcaj6hhb84a.us.auth0.com/.well-known/jwks.json"


# ---------------------------------------------------------- client side --
def test_client_reuses_one_token_across_runs_and_refreshes_once_on_401(api):
    el._TOKEN_CACHE.clear()
    c1 = el.MyobClient(session=api, base_url="http://testserver", token_url="http://testserver/oauth/token")
    c1.authenticate()
    c1.company_file()
    c2 = el.MyobClient(session=api, base_url="http://testserver", token_url="http://testserver/oauth/token")
    c2.authenticate()                                                     # second run in the same process: cached token
    assert c1.token_requests == 1 and c2.token_requests == 0
    c2.token = _issuer(api).issue(CID, A.ALL_SCOPES, iat=int(time.time()) - 7200, exp=int(time.time()) - 3600)
    assert c2.company_file()["Id"]                                        # 401 -> one fresh token -> success
    assert c2.token_requests == 1


def test_token_endpoint_accepts_client_secret_basic_like_auth0(api):
    """n8n's 'Get Token' node sends the client secret via an encrypted Basic Auth credential, not in the workflow JSON."""
    basic = base64.b64encode(f"{CID}:mock-client-secret".encode()).decode()
    r = api.post("/oauth/token", data={"grant_type": "client_credentials", "audience": "https://myob-mock.dagostino-demo"},
                 headers={"Authorization": f"Basic {basic}"})
    assert r.status_code == 200 and _get(api, r.json()["access_token"]).status_code == 200
    bad = base64.b64encode(f"{CID}:wrong".encode()).decode()
    assert api.post("/oauth/token", data={"grant_type": "client_credentials"}, headers={"Authorization": f"Basic {bad}"}).status_code == 401


def test_n8n_workflows_keep_secrets_in_credentials_not_json():
    for f in ("myob_to_snowflake_local.json", "myob_to_snowflake_cloud.json"):
        wf = json.loads((ROOT / "integration" / "n8n" / f).read_text(encoding="utf-8"))
        text = json.dumps(wf)
        assert "client_secret" not in text.replace("client_secret_basic", "") and "mock-client-secret" not in text
        tok = next(n for n in wf["nodes"] if n["name"] == "Get Token")
        assert tok["parameters"]["genericAuthType"] == "httpBasicAuth" and "httpBasicAuth" in tok["credentials"]
    cloud = json.loads((ROOT / "integration" / "n8n" / "myob_to_snowflake_cloud.json").read_text(encoding="utf-8"))
    assert "auth0.com/oauth/token" in json.dumps(cloud)
