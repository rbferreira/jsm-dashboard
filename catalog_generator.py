"""
catalog_generator.py — One-time script to analyze SDL tickets via Claude API
and generate a structured Service Catalog for JSM.

Usage:
    python catalog_generator.py
    # or inside container:
    podman exec -it sd-dashboard python catalog_generator.py
"""

import csv
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

import jira_client

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CLAUDE_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CATALOG_JSON = OUTPUT_DIR / "catalog.json"
CATALOG_CSV = OUTPUT_DIR / "catalog.csv"
CATALOG_MD = OUTPUT_DIR / "catalog.md"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Você é um especialista em ITSM e Jira Service Management.
Sua tarefa é analisar chamados de um service desk de logística e os request types existentes,
e propor um catálogo de serviços moderno e bem estruturado para o portal JSM.

Sempre retorne um JSON válido, sem markdown, sem texto extra. Apenas o JSON puro."""

CATALOG_PROMPT = """Analise os chamados do service desk e os request types existentes do portal JSM.

Com base nos dados fornecidos:
1. Categorize os chamados por tipo/assunto
2. Identifique grupos de serviços relacionados
3. Proponha um novo catálogo de serviços com hierarquia: Categorias > Grupos > Tipos de chamado
4. Para cada tipo sugerido, inclua: nome, descrição, grupo responsável, campos sugeridos para o formulário
5. Para cada ticket analisado, atribua uma categoria, grupo e tipo sugerido

Retorne APENAS um JSON com esta estrutura exata:
{{
  "catalog": [
    {{
      "name": "Nome da Categoria",
      "groups": [
        {{
          "name": "Nome do Grupo",
          "types": [
            {{
              "name": "Nome do Tipo de Chamado",
              "description": "Descrição do serviço",
              "responsible_team": "Time responsável",
              "form_fields": ["campo1", "campo2"]
            }}
          ]
        }}
      ]
    }}
  ],
  "tickets": [
    {{
      "ticket_id": "SDL-XXXXX",
      "summary": "resumo do ticket",
      "categoria": "Nome da Categoria",
      "grupo": "Nome do Grupo",
      "tipo_sugerido": "Nome do Tipo de Chamado"
    }}
  ]
}}

Dados dos chamados (último ano):
{tickets}

Request types atuais do portal:
{request_types}
"""


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_tickets() -> list[dict]:
    """Fetch all SDL tickets from the last year.

    Returns:
        List of Jira issue dicts.
    """
    logger.info("Buscando chamados do último ano...")
    jql = f'project = {jira_client.PROJECT} AND created >= -365d ORDER BY created ASC'
    fields = ["summary", "description", "issuetype", "status", "created", "assignee", "priority"]
    issues = jira_client.search_all_issues(jql, fields)
    logger.info("  %d chamados encontrados.", len(issues))
    return issues


def fetch_request_types() -> list[dict]:
    """Fetch current JSM request types.

    Returns:
        List of request type dicts from the JSM portal.
    """
    logger.info("Buscando request types do portal JSM...")
    sd_id = jira_client.get_service_desk_id()
    if not sd_id:
        logger.warning("  Service desk ID não encontrado. Continuando sem request types.")
        return []
    rts = jira_client.get_request_types(sd_id)
    logger.info("  %d request types encontrados.", len(rts))
    return rts


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def _format_tickets_for_prompt(issues: list[dict]) -> str:
    """Format issue list into a compact JSON string for the prompt.

    Args:
        issues: List of Jira issue dicts.

    Returns:
        JSON string with id, summary, type, and status for each issue.
    """
    rows = []
    for issue in issues:
        f = issue.get("fields", {})
        rows.append({
            "id": issue.get("key", ""),
            "summary": f.get("summary", "")[:120],
            "type": (f.get("issuetype") or {}).get("name", ""),
            "status": (f.get("status") or {}).get("name", ""),
        })
    return json.dumps(rows, ensure_ascii=False)


def _format_request_types_for_prompt(rts: list[dict]) -> str:
    """Format request types into a compact JSON string for the prompt.

    Args:
        rts: List of JSM request type dicts.

    Returns:
        JSON string with name and description for each request type.
    """
    rows = [{"name": rt.get("name", ""), "description": rt.get("description", "")} for rt in rts]
    return json.dumps(rows, ensure_ascii=False)


def _build_batches(tickets: list[dict], batch_size: int = 500) -> list[list[dict]]:
    """Split tickets into batches to fit within context limits.

    Args:
        tickets: Full list of Jira issue dicts.
        batch_size: Maximum number of tickets per batch (default 500).

    Returns:
        List of ticket sub-lists.
    """
    return [tickets[i:i + batch_size] for i in range(0, len(tickets), batch_size)]


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> str:
    """Extract JSON from text, handling markdown code fences.

    Tries to find a JSON object inside triple-backtick fences first; falls
    back to locating the outermost ``{`` … ``}`` pair in the raw text.

    Args:
        text: Raw string potentially containing JSON.

    Returns:
        Candidate JSON string (may still be invalid; caller must parse it).
    """
    fence_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if fence_match:
        return fence_match.group(1)
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


# ---------------------------------------------------------------------------
# Claude API calls
# ---------------------------------------------------------------------------

def call_claude_streaming(prompt: str) -> str:
    """Call Claude API with streaming and adaptive thinking.

    Args:
        prompt: User-facing prompt text.

    Returns:
        Full response text (stripped of leading/trailing whitespace).

    Raises:
        ValueError: If ``ANTHROPIC_API_KEY`` is not set.
        anthropic.APIError: On API-level failures.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY não configurado no .env")

    client = anthropic.Anthropic(api_key=api_key)

    logger.info("Chamando Claude API (streaming, modelo=%s)...", CLAUDE_MODEL)
    full_text = ""

    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=64000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for event in stream:
            if event.type == "content_block_start":
                if event.content_block.type == "thinking":
                    print("  [Pensando...]", flush=True)
                elif event.content_block.type == "text":
                    print("  [Gerando catálogo...]", flush=True)
            elif event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    full_text += event.delta.text
                    print(".", end="", flush=True)

        final = stream.get_final_message()
        usage = final.usage
        print(
            f"\n  Tokens: {usage.input_tokens} entrada / {usage.output_tokens} saída",
            flush=True,
        )

    return full_text.strip()


def call_claude_with_retry(prompt: str, max_retries: int = 3) -> str:
    """Call Claude API with automatic retry on transient failures.

    Args:
        prompt: User-facing prompt text.
        max_retries: Maximum number of attempts (default 3).

    Returns:
        Full response text from Claude.

    Raises:
        Exception: Re-raises the last exception after all retries are exhausted.
    """
    for attempt in range(max_retries):
        try:
            return call_claude_streaming(prompt)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"  Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...", flush=True)
            time.sleep(wait)
    # Unreachable, but satisfies type checkers
    raise RuntimeError("Exhausted retries")  # pragma: no cover


# ---------------------------------------------------------------------------
# Result merging
# ---------------------------------------------------------------------------

def merge_batch_results(results: list[dict]) -> dict:
    """Merge multiple batch JSON results into a single catalog + tickets structure.

    Duplicate categories and groups are merged; duplicate service types (by
    name) within the same group are deduplicated.

    Args:
        results: List of parsed JSON dicts, each with ``catalog`` and
            ``tickets`` keys.

    Returns:
        Single merged dict with ``catalog`` (list) and ``tickets`` (list).
    """
    merged_catalog: dict[str, dict] = {}
    merged_tickets: list[dict] = []

    for result in results:
        for cat in result.get("catalog", []):
            cat_name = cat["name"]
            if cat_name not in merged_catalog:
                merged_catalog[cat_name] = {"name": cat_name, "groups": {}}
            for grp in cat.get("groups", []):
                grp_name = grp["name"]
                if grp_name not in merged_catalog[cat_name]["groups"]:
                    merged_catalog[cat_name]["groups"][grp_name] = {"name": grp_name, "types": []}
                existing_types = {t["name"] for t in merged_catalog[cat_name]["groups"][grp_name]["types"]}
                for t in grp.get("types", []):
                    if t["name"] not in existing_types:
                        merged_catalog[cat_name]["groups"][grp_name]["types"].append(t)
                        existing_types.add(t["name"])

        merged_tickets.extend(result.get("tickets", []))

    catalog_list = []
    for cat in merged_catalog.values():
        catalog_list.append({
            "name": cat["name"],
            "groups": list(cat["groups"].values()),
        })

    return {"catalog": catalog_list, "tickets": merged_tickets}


# ---------------------------------------------------------------------------
# Output serialisers
# ---------------------------------------------------------------------------

def save_json(data: dict) -> None:
    """Write the full catalog structure to a JSON file.

    Args:
        data: Merged catalog dict.
    """
    with open(CATALOG_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Salvo: %s", CATALOG_JSON)


def save_csv(tickets: list[dict]) -> None:
    """Write the classified tickets to a CSV file.

    Args:
        tickets: List of ticket classification dicts.
    """
    fieldnames = ["ticket_id", "summary", "categoria", "grupo", "tipo_sugerido"]
    with open(CATALOG_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(tickets)
    logger.info("Salvo: %s", CATALOG_CSV)


def save_markdown(data: dict) -> None:
    """Write a human-readable Markdown report of the service catalog.

    Args:
        data: Merged catalog dict with ``catalog`` and ``tickets`` keys.
    """
    lines = ["# Catálogo de Serviços SDL — HelpMe\n"]
    lines.append(f"> Gerado automaticamente via análise de {len(data.get('tickets', []))} chamados.\n")

    for cat in data.get("catalog", []):
        lines.append(f"\n## Categoria: {cat['name']}\n")
        for grp in cat.get("groups", []):
            lines.append(f"\n### Grupo: {grp['name']}\n")
            for t in grp.get("types", []):
                lines.append(f"- **{t['name']}**")
                if t.get("description"):
                    lines.append(f"  - Descrição: {t['description']}")
                if t.get("responsible_team"):
                    lines.append(f"  - Responsável: {t['responsible_team']}")
                if t.get("form_fields"):
                    lines.append(f"  - Campos: {', '.join(t['form_fields'])}")

    lines.append("\n---\n\n## Tickets Categorizados\n")
    lines.append("| Ticket | Resumo | Categoria | Grupo | Tipo Sugerido |")
    lines.append("|--------|--------|-----------|-------|---------------|")
    for t in data.get("tickets", [])[:200]:  # limit table for readability
        row = "| {} | {} | {} | {} | {} |".format(
            t.get("ticket_id", ""),
            (t.get("summary", "") or "")[:60].replace("|", "/"),
            t.get("categoria", ""),
            t.get("grupo", ""),
            t.get("tipo_sugerido", ""),
        )
        lines.append(row)

    if len(data.get("tickets", [])) > 200:
        lines.append(f"\n> Exibindo 200 de {len(data['tickets'])} tickets. Veja o CSV para a lista completa.")

    with open(CATALOG_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info("Salvo: %s", CATALOG_MD)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("SDL Catalog Generator — HelpMe")
    print("=" * 60)

    # 1. Fetch data
    tickets = fetch_tickets()
    request_types = fetch_request_types()
    rt_str = _format_request_types_for_prompt(request_types)

    # 2. Process in batches
    batches = _build_batches(tickets, batch_size=500)
    logger.info("Processando %d batch(es) de tickets...", len(batches))

    batch_results: list[dict] = []

    for i, batch in enumerate(batches, 1):
        print(f"--- Batch {i}/{len(batches)} ({len(batch)} tickets) ---", flush=True)
        tickets_str = _format_tickets_for_prompt(batch)
        prompt = CATALOG_PROMPT.format(tickets=tickets_str, request_types=rt_str)

        try:
            raw = call_claude_with_retry(prompt)
            json_str = _extract_json(raw)
            parsed = json.loads(json_str.strip())
            batch_results.append(parsed)

        except json.JSONDecodeError as exc:
            logger.warning("Erro ao parsear JSON do batch %d: %s", i, exc)
            logger.warning("Resposta recebida (primeiros 500 chars): %s", raw[:500])
            # Skip this batch but continue processing the rest
        except Exception as exc:
            logger.error("Erro no batch %d: %s. Pulando.", i, exc)

    if not batch_results:
        logger.error("Nenhum resultado obtido. Verifique os logs acima.")
        sys.exit(1)

    # 3. Merge and save
    logger.info("Merging resultados...")
    merged = merge_batch_results(batch_results)

    save_json(merged)
    save_csv(merged.get("tickets", []))
    save_markdown(merged)

    print("\n" + "=" * 60)
    print("Catálogo gerado com sucesso!")
    print(f"  Categorias: {len(merged.get('catalog', []))}")
    print(f"  Tickets categorizados: {len(merged.get('tickets', []))}")
    print(f"  Arquivos em: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
