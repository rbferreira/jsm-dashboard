"""Script de diagnóstico da integração Jira API.

Roda fora do container — testa cada etapa isoladamente e imprime o resultado raw.
Uso: python test_jira.py
"""

import base64
import json
import os
import sys

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()

BASE_URL = os.getenv("JIRA_BASE_URL", "https://your-instance.atlassian.net")
EMAIL = os.getenv("JIRA_EMAIL")
API_TOKEN = os.getenv("JIRA_API_TOKEN")
PROJECT = os.getenv("JIRA_PROJECT", "SDL")

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def pretty(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def section(n, title: str):
    print(f"\n{'='*60}")
    print(f"  Teste {n}: {title}")
    print("="*60)


# ---------------------------------------------------------------------------
# Diagnóstico de método de autenticação (Testes 0A, 0B, 0C)
# ---------------------------------------------------------------------------
MYSELF_URL = f"{BASE_URL}/rest/api/3/myself"
BASE_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

working_auth_kwargs: dict = {}  # será preenchido com o método que funcionar

# --- Teste 0A: Basic Auth (email:token) — método atual ---
section("0A", "Basic Auth email:token  ->  Authorization: Basic base64(email:token)")
try:
    r = requests.get(MYSELF_URL, auth=HTTPBasicAuth(EMAIL, API_TOKEN), headers=BASE_HEADERS, timeout=30)
    print(f"Status: {r.status_code}")
    if r.ok:
        data = r.json()
        print(f"{PASS} — logado como: {data.get('displayName')} ({data.get('emailAddress')})")
        working_auth_kwargs = {"auth": HTTPBasicAuth(EMAIL, API_TOKEN)}
    else:
        print(f"{FAIL} — resposta:\n{r.text}")
except Exception as e:
    print(f"{FAIL} — exceção: {e}")

# --- Teste 0B: Bearer Token --- (somente se 0A falhou)
if not working_auth_kwargs:
    section("0B", "Bearer Token  ->  Authorization: Bearer <api_token>")
    bearer_headers = {**BASE_HEADERS, "Authorization": f"Bearer {API_TOKEN}"}
    try:
        r = requests.get(MYSELF_URL, headers=bearer_headers, timeout=30)
        print(f"Status: {r.status_code}")
        if r.ok:
            data = r.json()
            print(f"{PASS} — logado como: {data.get('displayName')} ({data.get('emailAddress')})")
            working_auth_kwargs = {"headers": bearer_headers}
        else:
            print(f"{FAIL} — resposta:\n{r.text}")
    except Exception as e:
        print(f"{FAIL} — exceção: {e}")
else:
    section("0B", "Bearer Token — PULADO (0A já passou)")

# --- Teste 0C: Basic Auth token only (sem email) --- (somente se 0A e 0B falharam)
if not working_auth_kwargs:
    section("0C", "Basic Auth token-only  ->  Authorization: Basic base64(:token)")
    token_only = base64.b64encode(f":{API_TOKEN}".encode()).decode()
    token_only_headers = {**BASE_HEADERS, "Authorization": f"Basic {token_only}"}
    try:
        r = requests.get(MYSELF_URL, headers=token_only_headers, timeout=30)
        print(f"Status: {r.status_code}")
        if r.ok:
            data = r.json()
            print(f"{PASS} — logado como: {data.get('displayName')} ({data.get('emailAddress')})")
            working_auth_kwargs = {"headers": token_only_headers}
        else:
            print(f"{FAIL} — resposta:\n{r.text}")
    except Exception as e:
        print(f"{FAIL} — exceção: {e}")
else:
    section("0C", "Basic Auth token-only — PULADO (método anterior já passou)")

if not working_auth_kwargs:
    print(f"\n{FAIL} Nenhum método de autenticação funcionou. Verifique o token/credenciais.")
    sys.exit(1)

print(f"\n>>> Método de auth escolhido: {list(working_auth_kwargs.keys())}")

# Monta auth e headers para os próximos testes
if "auth" in working_auth_kwargs:
    auth = working_auth_kwargs["auth"]
    headers = BASE_HEADERS
else:
    auth = None
    headers = working_auth_kwargs["headers"]


def _get(url, **kwargs):
    return requests.get(url, auth=auth, headers=headers, timeout=30, **kwargs)


def _post(url, **kwargs):
    return requests.post(url, auth=auth, headers=headers, timeout=30, **kwargs)


# ---------------------------------------------------------------------------
# Teste 1 — Autenticação (resumo do método vencedor)
# ---------------------------------------------------------------------------
section(1, "Autenticação confirmada — método vencedor já identificado acima")
print(f"{PASS} — auth já verificada nos testes 0A/0B/0C acima.")

# ---------------------------------------------------------------------------
# Teste 2 — Projeto SDL existe e é acessível
# ---------------------------------------------------------------------------
section(2, f"Projeto {PROJECT} acessível (GET /rest/api/3/project/{PROJECT})")
try:
    r = _get(f"{BASE_URL}/rest/api/3/project/{PROJECT}")
    print(f"Status: {r.status_code}")
    if r.ok:
        data = r.json()
        print(f"{PASS} — projeto: {data.get('name')} | key: {data.get('key')} | tipo: {data.get('projectTypeKey')}")
    else:
        print(f"{FAIL} — resposta:\n{r.text}")
except Exception as e:
    print(f"{FAIL} — exceção: {e}")

# ---------------------------------------------------------------------------
# Teste 3 — POST /rest/api/3/search/jql (query mínima)
# ---------------------------------------------------------------------------
section(3, "POST /rest/api/3/search/jql — query mínima")
body3 = {
    "jql": f"project = {PROJECT} ORDER BY created DESC",
    "maxResults": 3,
    "fields": ["summary"],
}
print(f"Body enviado:\n{pretty(body3)}")
try:
    r = _post(f"{BASE_URL}/rest/api/3/search/jql", json=body3)
    print(f"\nStatus: {r.status_code}")
    if r.ok:
        data = r.json()
        issues = data.get("issues", [])
        print(f"{PASS} — issues retornados: {len(issues)}")
        print(f"Chaves top-level: {list(data.keys())}")
        print(f"Resposta completa:\n{pretty(data)}")
    else:
        print(f"{FAIL} — resposta:\n{r.text}")
except Exception as e:
    print(f"{FAIL} — exceção: {e}")

# ---------------------------------------------------------------------------
# Teste 4 — POST com filtro de data (formato YYYY-MM-DD)
# ---------------------------------------------------------------------------
section(4, "POST /rest/api/3/search/jql — filtro de data")
body4 = {
    "jql": f'project = {PROJECT} AND created >= "2026-03-14" AND created <= "2026-03-21" ORDER BY created ASC',
    "maxResults": 3,
    "fields": ["summary", "created"],
}
print(f"Body enviado:\n{pretty(body4)}")
try:
    r = _post(f"{BASE_URL}/rest/api/3/search/jql", json=body4)
    print(f"\nStatus: {r.status_code}")
    if r.ok:
        data = r.json()
        issues = data.get("issues", [])
        print(f"{PASS} — issues retornados: {len(issues)}")
        print(f"Resposta completa:\n{pretty(data)}")
    else:
        print(f"{FAIL} — resposta:\n{r.text}")
except Exception as e:
    print(f"{FAIL} — exceção: {e}")

# ---------------------------------------------------------------------------
# Teste 5 — GET /rest/api/3/search (endpoint antigo, fallback)
# ---------------------------------------------------------------------------
section(5, "GET /rest/api/3/search — endpoint antigo (fallback)")
params5 = {
    "jql": f"project = {PROJECT} ORDER BY created DESC",
    "maxResults": 3,
    "fields": "summary",
}
print(f"Params: {params5}")
try:
    r = _get(f"{BASE_URL}/rest/api/3/search", params=params5)
    print(f"\nStatus: {r.status_code}")
    if r.ok:
        data = r.json()
        issues = data.get("issues", [])
        total = data.get("total", "N/A")
        print(f"{PASS} — issues retornados: {len(issues)} | total: {total}")
        print(f"Chaves top-level: {list(data.keys())}")
    else:
        print(f"{FAIL} — resposta:\n{r.text}")
except Exception as e:
    print(f"{FAIL} — exceção: {e}")

# ---------------------------------------------------------------------------
# Teste 6 — Estrutura completa dos fields usados no dashboard
# ---------------------------------------------------------------------------
section(6, "Estrutura dos fields do dashboard — primeiro issue completo")
body6 = {
    "jql": f"project = {PROJECT} ORDER BY created DESC",
    "maxResults": 1,
    "fields": ["issuetype", "status", "assignee", "priority", "created", "resolutiondate", "summary"],
}
print(f"Body enviado:\n{pretty(body6)}")
try:
    r = _post(f"{BASE_URL}/rest/api/3/search/jql", json=body6)
    print(f"\nStatus: {r.status_code}")
    if r.ok:
        data = r.json()
        issues = data.get("issues", [])
        if issues:
            print(f"{PASS} — primeiro issue completo:\n{pretty(issues[0])}")
        else:
            print(f"{FAIL} — nenhum issue retornado. Resposta:\n{pretty(data)}")
    else:
        print(f"{FAIL} — resposta:\n{r.text}")
except Exception as e:
    print(f"{FAIL} — exceção: {e}")

print(f"\n{'='*60}")
print("  Diagnóstico concluído.")
print("="*60)
