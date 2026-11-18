"""Builds the n8n workflow JSON files (local Docker and n8n Cloud variants).

    python integration/n8n/build_workflows.py

Flow: daily 6am -> config -> clear landing -> read watermarks -> extract every MYOB resource (OAuth, paging, incremental)
-> insert landing rows -> promote to typed RAW with one INSERT ALL ... PARSE_JSON -> write load_audit + company file row
-> fail the execution if any resource's API count != rows loaded (n8n's error workflow then alerts).
"""
import json
from pathlib import Path


CONFIG_JS = r"""// Non-secret settings only. The client SECRET lives in the n8n credential on the "Get Token" node (encrypted by n8n),
// never in this JSON. clientId is not secret: it is sent as x-myobapi-key and must equal the token's azp claim.
return [{ json: {
  baseUrl: '__BASE_URL__',
  tokenUrl: '__TOKEN_URL__',
  audience: 'https://myob-mock.dagostino-demo',
  clientId: '__CLIENT_ID__',
  pageSize: 400,
  resources: [
    { path: 'GeneralLedger/Account',  table: 'myob_accounts' },
    { path: 'Contact/Customer',       table: 'myob_customers' },
    { path: 'Sale/Invoice/Service',   table: 'myob_invoices' },
    { path: 'Sale/CustomerPayment',   table: 'myob_customer_payments' },
  ],
}}];"""

EXTRACT_JS = r"""// Pull every resource from MYOB with paging + incremental watermark.
const cfg = $('Config').first().json;
const wmRows = $('Get Watermarks').all().map(i => i.json).filter(r => r.RESOURCE);
const watermarks = Object.fromEntries(wmRows.map(r => [r.RESOURCE, r.WATERMARK]));

const asJson = r => (typeof r === 'string' ? JSON.parse(r) : r);
const tok = $('Get Token').first().json;                // one OAuth token per run (Auth0 free plan meters M2M tokens)
const headers = {
  Authorization: `Bearer ${tok.access_token}`,
  'x-myobapi-key': cfg.clientId,
  'x-myobapi-version': 'v2',
  Accept: 'application/json',
};

const companyFiles = asJson(await this.helpers.httpRequest({ method: 'GET', url: `${cfg.baseUrl}/accountright/`, headers }));
const cf = companyFiles[0];

const batchId = $execution.id + '-' + Date.now();
const loadedAt = new Date().toISOString().slice(0, 19);
const rows = [], audits = [];

for (const res of cfg.resources) {
  const since = watermarks[res.path] || null;
  let url = `${cfg.baseUrl}/accountright/${cf.Id}/${res.path}?$top=${cfg.pageSize}`;
  if (since) url += `&$filter=${encodeURIComponent(`LastModified gt datetime'${since}'`)}`;
  let items = [], apiCount = null, status = 'OK';
  try {
    while (url) {
      const body = asJson(await this.helpers.httpRequest({ method: 'GET', url, headers }));
      items = items.concat(body.Items);
      apiCount = body.Count ?? apiCount;
      url = body.NextPageLink;
    }
    if (apiCount !== items.length) status = 'COUNT_MISMATCH';
  } catch (e) {
    status = ('ERROR: ' + e.message).slice(0, 200); apiCount = -1; items = [];
  }
  for (const it of items) {
    rows.push({ TARGET_TABLE: res.table, RECORD_UID: it.UID, PAYLOAD_TEXT: JSON.stringify(it),
                LAST_MODIFIED: it.LastModified, BATCH_ID: batchId, LOADED_AT: loadedAt });
  }
  const newWm = items.reduce((m, it) => (it.LastModified > (m || '') ? it.LastModified : m), since);
  audits.push({ BATCH_ID: batchId, RESOURCE: res.path, API_COUNT: apiCount,
                LOADED_COUNT: items.length, WATERMARK: newWm, STATUS: status, LOADED_AT: loadedAt });
}
const company = { COMPANY_FILE_UID: cf.Id, NAME: cf.Name, LAST_SYNC_DATE: cf.LastSyncDate, BATCH_ID: batchId, LOADED_AT: loadedAt };
return [{ json: { batchId, rows, audits, company } }];"""

LANDING_JS = r"""const rows = $('Extract from MYOB').first().json.rows;
return rows.length ? rows.map(r => ({ json: r })) : [{ json: { EMPTY: true } }];"""

AUDIT_JS = r"""return $('Extract from MYOB').first().json.audits.map(a => ({ json: a }));"""

COMPANY_JS = r"""return [{ json: $('Extract from MYOB').first().json.company }];"""

CHECK_JS = r"""const bad = $('Extract from MYOB').first().json.audits.filter(a => a.STATUS !== 'OK');
if (bad.length) {
  throw new Error('MYOB load problems: ' + bad.map(b => `${b.RESOURCE}=${b.STATUS}`).join('; '));
}
return [{ json: { ok: true, loaded: $('Extract from MYOB').first().json.rows.length } }];"""

PROMOTE_SQL = """insert all
  when target_table = 'myob_accounts'          then into raw.myob_accounts          values (record_uid, payload, last_modified, batch_id, loaded_at)
  when target_table = 'myob_customers'         then into raw.myob_customers         values (record_uid, payload, last_modified, batch_id, loaded_at)
  when target_table = 'myob_invoices'          then into raw.myob_invoices          values (record_uid, payload, last_modified, batch_id, loaded_at)
  when target_table = 'myob_customer_payments' then into raw.myob_customer_payments values (record_uid, payload, last_modified, batch_id, loaded_at)
select target_table, record_uid, parse_json(payload_text) as payload, last_modified, batch_id, loaded_at
from raw.myob_landing
where batch_id = '{{ $('Extract from MYOB').first().json.batchId }}'"""

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
    node("Extract from MYOB", "n8n-nodes-base.code", 2, [880, 300], {"jsCode": EXTRACT_JS}),
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
         ("Get Watermarks", "Get Token"), ("Get Token", "Extract from MYOB"), ("Extract from MYOB", "Landing Rows"),
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
            "myob_to_snowflake_cloud.json": ("MYOB → Snowflake (daily incremental) [n8n Cloud + Auth0]", "https://REPLACE-WITH-PUBLIC-MOCK-API-URL",
                                             "https://dev-z1apvxcaj6hhb84a.us.auth0.com/oauth/token", "REPLACE-WITH-AUTH0-M2M-CLIENT-ID")}
HERE = Path(__file__).resolve().parent
for fname, (title, base, token_url, client_id) in VARIANTS.items():
    js = json.dumps(nodes).replace("__BASE_URL__", base).replace("__TOKEN_URL__", token_url).replace("__CLIENT_ID__", client_id)
    wf = {"name": title, "nodes": json.loads(js), "connections": conns,
          "settings": {"executionOrder": "v1", "timezone": "Australia/Sydney"}, "active": False, "pinData": {}}
    (HERE / fname).write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")
    print(fname, len(nodes), "nodes")
