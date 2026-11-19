"""Builds the n8n workflow JSON files (local Docker and n8n Cloud variants).

    python integration/n8n/build_workflows.py

Flow: daily 6am -> config -> clear landing -> read watermarks -> extract every MYOB resource (OAuth, paging, incremental)
-> insert landing rows -> promote to typed RAW with one INSERT ALL ... PARSE_JSON -> write load_audit + company file row
-> fail the execution if any resource's API count != rows loaded (n8n's error workflow then alerts).
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from integration.extract_load import SOURCES  # noqa: E402

SOURCES_JS = json.dumps([{**asdict(s), "page_params": dict(s.page_params)} for s in SOURCES])


CONFIG_JS_TEMPLATE = r"""// Non-secret settings only. The client SECRET lives in the n8n credential on the "Get Token" node (encrypted by n8n),
// never in this JSON. clientId is not secret: it is sent as the API-key header and must equal the token's azp claim.
// `sources` is generated from integration/extract_load.py SOURCES, so n8n and the Python loader share one definition.
return [{ json: {
  baseUrl: '__BASE_URL__',
  tokenUrl: '__TOKEN_URL__',
  audience: 'https://myob-mock.dagostino-demo',
  clientId: '__CLIENT_ID__',
  sources: __SOURCES__,
}}];"""

CONFIG_JS = CONFIG_JS_TEMPLATE.replace('__SOURCES__', SOURCES_JS)

EXTRACT_JS = r"""// Pull every source (MYOB, LEAP, triConvey, InfoTrack, PEXA) with its own paging style + incremental watermark.
const cfg = $('Config').first().json;
const wmRows = $('Get Watermarks').all().map(i => i.json).filter(r => r.RESOURCE);
const watermarks = Object.fromEntries(wmRows.map(r => [r.RESOURCE, r.WATERMARK]));
const asJson = r => (typeof r === 'string' ? JSON.parse(r) : r);
const dig = (o, path) => path.split('.').reduce((v, k) => (v == null ? v : v[k]), o);
const tok = $('Get Token').first().json;                // one OAuth token per run (Auth0 free plan meters M2M tokens)
const headersFor = src => {
  const h = { Authorization: `Bearer ${tok.access_token}`, Accept: 'application/json' };
  if (src.myob) { h['x-myobapi-key'] = cfg.clientId; h['x-myobapi-version'] = 'v2'; }
  else if (src.key_header) { h[src.key_header] = cfg.clientId; }
  return h;
};
const myobHeaders = headersFor({ myob: true });
const cf = asJson(await this.helpers.httpRequest({ method: 'GET', url: `${cfg.baseUrl}/accountright/`, headers: myobHeaders }))[0];

const batchId = $execution.id + '-' + Date.now();
const loadedAt = new Date().toISOString().slice(0, 19);
const rows = [], audits = [];

for (const src of cfg.sources) {
  const since = watermarks[src.resource] || null;
  const params = { ...src.page_params };                 // n8n Cloud's Code sandbox has no URLSearchParams
  if (since) params[src.since_param] = src.myob ? `LastModified gt datetime'${since}'` : since;
  const qs = Object.entries(params).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
  let url = `${cfg.baseUrl}${src.path.replace('{cf}', cf.Id)}?${qs}`;
  let items = [], apiCount = null, status = 'OK';
  try {
    while (url) {
      const body = asJson(await this.helpers.httpRequest({ method: 'GET', url, headers: headersFor(src) }));
      items = items.concat(body[src.items]);
      apiCount = dig(body, src.count) ?? apiCount;
      url = dig(body, src.next);
    }
    if (apiCount !== items.length) status = 'COUNT_MISMATCH';
  } catch (e) {
    status = ('ERROR: ' + e.message).slice(0, 200); apiCount = -1; items = [];
  }
  for (const it of items) {
    rows.push({ TARGET_TABLE: src.table, RECORD_UID: String(it[src.id_key]), PAYLOAD_TEXT: JSON.stringify(it),
                LAST_MODIFIED: it[src.updated], BATCH_ID: batchId, LOADED_AT: loadedAt });
  }
  const newWm = items.reduce((m, it) => (it[src.updated] && it[src.updated] > (m || '') ? it[src.updated] : m), since);
  audits.push({ BATCH_ID: batchId, RESOURCE: src.resource, API_COUNT: apiCount,
                LOADED_COUNT: items.length, WATERMARK: newWm, STATUS: status, LOADED_AT: loadedAt });
}
const company = { COMPANY_FILE_UID: cf.Id, NAME: cf.Name, LAST_SYNC_DATE: cf.LastSyncDate, BATCH_ID: batchId, LOADED_AT: loadedAt };
return [{ json: { batchId, rows, audits, company } }];"""

LANDING_JS = r"""const rows = $('Extract from Sources').first().json.rows;
return rows.length ? rows.map(r => ({ json: r })) : [{ json: { EMPTY: true } }];"""

AUDIT_JS = r"""return $('Extract from Sources').first().json.audits.map(a => ({ json: a }));"""

COMPANY_JS = r"""return [{ json: $('Extract from Sources').first().json.company }];"""

CHECK_JS = r"""const bad = $('Extract from Sources').first().json.audits.filter(a => a.STATUS !== 'OK');
if (bad.length) {
  throw new Error('Load problems: ' + bad.map(b => `${b.RESOURCE}=${b.STATUS}`).join('; '));
}
return [{ json: { ok: true, loaded: $('Extract from Sources').first().json.rows.length } }];"""

PROMOTE_SQL = ("insert all\n" + "".join(
    f"  when target_table = '{t}' then into raw.{t} values (record_uid, payload, last_modified, batch_id, loaded_at)\n"
    for t in [src.table for src in SOURCES]) +
    "select target_table, record_uid, parse_json(payload_text) as payload, last_modified, batch_id, loaded_at\n"
    "from raw.myob_landing\n"
    "where batch_id = '{{ $('Extract from Sources').first().json.batchId }}'")

SF_CRED = {"snowflake": {"id": "REPLACE_ME", "name": "Snowflake account"}}

def node(name, typ, ver, pos, params, **extra):
    n = {"parameters": params, "name": name, "type": typ, "typeVersion": ver, "position": pos}
    n.update(extra)
    return n

nodes = [
    node("Daily 6am", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 300],
         {"rule": {"interval": [{"triggerAtHour": 6}]}}),
    node("Config", "n8n-nodes-base.code", 2, [220, 300], {"jsCode": CONFIG_JS}),
    node("Clear Landing", "n8n-nodes-base.snowflake", 1, [440, 300],
         {"operation": "executeQuery", "query": "truncate table if exists raw.myob_landing"},
         credentials=SF_CRED, executeOnce=True),
    node("Get Watermarks", "n8n-nodes-base.snowflake", 1, [660, 300],
         {"operation": "executeQuery",
          "query": "select resource, max(watermark) as watermark from raw.load_audit where status = 'OK' group by resource"},
         credentials=SF_CRED, executeOnce=True, alwaysOutputData=True),
    node("Get Token", "n8n-nodes-base.httpRequest", 4.2, [880, 300], {
        "method": "POST", "url": "={{ $('Config').first().json.tokenUrl }}",
        "authentication": "genericCredentialType", "genericAuthType": "httpBasicAuth",
        "sendBody": True, "contentType": "form-urlencoded",
        "bodyParameters": {"parameters": [{"name": "grant_type", "value": "client_credentials"},
                                          {"name": "audience", "value": "={{ $('Config').first().json.audience }}"}]},
        "options": {}},
         credentials={"httpBasicAuth": {"id": "REPLACE_ME", "name": "MYOB API client (Basic Auth: client id + secret)"}}, executeOnce=True),
    node("Extract from Sources", "n8n-nodes-base.code", 2, [880, 300], {"jsCode": EXTRACT_JS}),
    node("Landing Rows", "n8n-nodes-base.code", 2, [1100, 300], {"jsCode": LANDING_JS}),
    node("Has New Rows?", "n8n-nodes-base.if", 2, [1320, 300], {
        "conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"},
                       "combinator": "and",
                       "conditions": [{"leftValue": "={{ $json.RECORD_UID }}", "rightValue": "",
                                       "operator": {"type": "string", "operation": "exists",
                                                    "singleValue": True}}]},
        "options": {}}),
    node("Insert Landing", "n8n-nodes-base.snowflake", 1, [1540, 200],
         {"operation": "insert", "table": "RAW.MYOB_LANDING",
          "columns": "TARGET_TABLE,RECORD_UID,PAYLOAD_TEXT,LAST_MODIFIED,BATCH_ID,LOADED_AT"},
         credentials=SF_CRED),
    node("Promote to RAW", "n8n-nodes-base.snowflake", 1, [1760, 200],
         {"operation": "executeQuery", "query": "=" + PROMOTE_SQL},
         credentials=SF_CRED, executeOnce=True),
    node("Audit Rows", "n8n-nodes-base.code", 2, [1980, 300], {"jsCode": AUDIT_JS}),
    node("Insert Audit", "n8n-nodes-base.snowflake", 1, [2200, 300],
         {"operation": "insert", "table": "RAW.LOAD_AUDIT",
          "columns": "BATCH_ID,RESOURCE,API_COUNT,LOADED_COUNT,WATERMARK,STATUS,LOADED_AT"},
         credentials=SF_CRED),
    node("Company File Row", "n8n-nodes-base.code", 2, [2420, 300], {"jsCode": COMPANY_JS}),
    node("Insert Company File", "n8n-nodes-base.snowflake", 1, [2640, 300],
         {"operation": "insert", "table": "RAW.MYOB_COMPANY_FILE", "columns": "COMPANY_FILE_UID,NAME,LAST_SYNC_DATE,BATCH_ID,LOADED_AT"},
         credentials=SF_CRED),
    node("Fail If Mismatch", "n8n-nodes-base.code", 2, [2860, 300], {"jsCode": CHECK_JS}),
]

def link(a, b, out_idx=0):
    return a, b, out_idx

edges = [("Daily 6am", "Config"), ("Config", "Clear Landing"), ("Clear Landing", "Get Watermarks"),
         ("Get Watermarks", "Get Token"), ("Get Token", "Extract from Sources"), ("Extract from Sources", "Landing Rows"),
         ("Landing Rows", "Has New Rows?"), ("Insert Landing", "Promote to RAW"),
         ("Promote to RAW", "Audit Rows"), ("Audit Rows", "Insert Audit"),
         ("Insert Audit", "Company File Row"), ("Company File Row", "Insert Company File"),
         ("Insert Company File", "Fail If Mismatch")]
conns = {}
for a, b in edges:
    conns.setdefault(a, {"main": [[]]})["main"][0].append({"node": b, "type": "main", "index": 0})
conns["Has New Rows?"] = {"main": [
    [{"node": "Insert Landing", "type": "main", "index": 0}],
    [{"node": "Audit Rows", "type": "main", "index": 0}]]}

for n in nodes:                                        # make room for "Get Token" between watermarks and extract
    if n["name"] != "Get Token" and n["position"][0] >= 880:
        n["position"] = [n["position"][0] + 220, n["position"][1]]

# (title, API base URL, token URL, client id). Cloud: tokens from Auth0 (free plan), API hosted on a public URL.
VARIANTS = {"myob_to_snowflake_local.json": ("MYOB → Snowflake (daily incremental) [local Docker]", "http://host.docker.internal:8000",
                                             "http://host.docker.internal:8000/oauth/token", "mock-client-id"),
            "myob_to_snowflake_cloud.json": ("MYOB → Snowflake (daily incremental) [n8n Cloud + Auth0]", "https://law-firm-mock-api.onrender.com",
                                             "https://dev-z1apvxcaj6hhb84a.us.auth0.com/oauth/token", "MjnrZgi6bRgIO4lbMUmhjYsrS3htKpv9")}
HERE = Path(__file__).resolve().parent
for fname, (title, base, token_url, client_id) in VARIANTS.items():
    js = json.dumps(nodes).replace("__BASE_URL__", base).replace("__TOKEN_URL__", token_url).replace("__CLIENT_ID__", client_id)
    wf = {"name": title, "nodes": json.loads(js), "connections": conns,
          "settings": {"executionOrder": "v1", "timezone": "Australia/Sydney"}, "active": False, "pinData": {}}
    (HERE / fname).write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")
    print(fname, len(nodes), "nodes")
