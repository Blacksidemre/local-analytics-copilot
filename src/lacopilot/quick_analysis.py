from __future__ import annotations

import json
import re
from typing import Any

from lacopilot.config import get_settings
from lacopilot.security import validate_local_model_name, validate_ollama_endpoint

_FINDING_CITATION = re.compile(r"\[(profile\.[A-Za-z0-9_.-]+)\]")
_NUMERIC_CLAIM = re.compile(r"(?<![\w.])[+-]?\d+(?:[.,]\d+)?(?:\s*%)?")
_QUICK_CARD_FINDING_IDS = (
    "profile.shape.rows",
    "profile.shape.columns",
    "profile.quality.missing_cells",
    "profile.quality.exact_duplicate_copies",
    "profile.quality.score_heuristic",
)
_ROLE_ORDER = ("numeric", "categorical", "datetime", "identifier", "text", "boolean")


def build_quick_dashboard(profile: dict[str, Any]) -> dict[str, Any]:
    """Build the deterministic UI contract for Quick mode.

    Cards are selected by stable finding IDs, never by column order or display label.
    The payload intentionally contains no raw rows or sample values.
    """
    finding_index = {
        finding["finding_id"]: finding
        for finding in profile.get("findings", [])
        if isinstance(finding, dict) and isinstance(finding.get("finding_id"), str)
    }
    missing_card_ids = [
        finding_id for finding_id in _QUICK_CARD_FINDING_IDS if finding_id not in finding_index
    ]
    if missing_card_ids:
        raise ValueError(
            "Quick dashboard için zorunlu finding kimlikleri eksik: " + ", ".join(missing_card_ids)
        )

    missing_finding_ids = {
        finding.get("dimension", {}).get("column"): finding["finding_id"]
        for finding in profile.get("findings", [])
        if finding.get("finding_id", "").startswith("profile.quality.missing.column.")
    }
    missing_by_column = sorted(
        (
            {
                "finding_id": missing_finding_ids[column],
                "column": column,
                "count": int(count),
                "pct": float(profile.get("missing_pct", {}).get(column, 0.0)),
            }
            for column, count in profile.get("missing_count", {}).items()
            if int(count) > 0 and column in missing_finding_ids
        ),
        key=lambda item: (-item["count"], item["column"].casefold()),
    )
    role_counts = [
        {"role": role, "count": len(profile.get("roles", {}).get(role, []))}
        for role in _ROLE_ORDER
        if role in profile.get("roles", {})
    ]
    ingestion = profile.get("ingestion", {})
    ingestion_summary = {
        key: ingestion[key]
        for key in ("format", "source_name", "size_bytes", "parser", "parser_version")
        if key in ingestion
    }
    if "csv" in ingestion:
        csv_meta = ingestion["csv"]
        ingestion_summary["csv"] = {
            key: csv_meta[key]
            for key in (
                "encoding",
                "delimiter_name",
                "decimal_separator",
                "expected_columns",
                "confidence",
                "warnings",
            )
            if key in csv_meta
        }
    if "excel" in ingestion:
        excel_meta = ingestion["excel"]
        ingestion_summary["excel"] = {
            key: excel_meta[key]
            for key in ("selected_sheet", "header_row", "sheet_count")
            if key in excel_meta
        }

    cards = [dict(finding_index[finding_id]) for finding_id in _QUICK_CARD_FINDING_IDS]
    warnings = [
        finding["warning"]
        for finding in cards
        if isinstance(finding.get("warning"), str) and finding["warning"]
    ]
    warnings.extend(str(note) for note in profile.get("notes", []) if note)
    return {
        "dashboard_version": 1,
        "title": "Hızlı Veri Profili",
        "cards": cards,
        "missing_by_column": missing_by_column,
        "role_counts": role_counts,
        "constant_columns": list(profile.get("constant_columns", [])),
        "ingestion": ingestion_summary,
        "warnings": list(dict.fromkeys(warnings)),
        "evidence_policy": "all_numeric_cards_bound_to_finding_id",
    }


def profile_digest(profile: dict[str, Any]) -> dict[str, Any]:
    missing_findings = {
        finding.get("dimension", {}).get("column"): finding["finding_id"]
        for finding in profile["findings"]
        if finding["finding_id"].startswith("profile.quality.missing.column.")
    }
    missing = [
        {
            "finding_id": missing_findings[column],
            "column": column,
            "count": count,
            "pct": profile["missing_pct"].get(column, 0.0),
        }
        for column, count in profile["missing_count"].items()
        if count
    ]
    return {
        "rows": profile["rows"],
        "columns": profile["columns"],
        "total_missing_cells": profile["total_missing_cells"],
        "missing_by_column": missing[:30],
        "exact_duplicate_copies": profile["duplicate_rows"],
        "duplicate_rows_including_originals": profile["duplicate_rows_including_originals"],
        "constant_columns": profile["constant_columns"],
        "roles": profile["roles"],
        "date_ranges": profile["date_ranges"],
        "quality_score_heuristic": profile["quality_score_heuristic"],
        "quality_score_warning": "Tarama amaçlı heuristiktir; denetim görüşü değildir.",
        "finding_ids": [finding["finding_id"] for finding in profile["findings"]],
        "ingestion": profile["ingestion"],
    }


def build_interpretation_messages(
    profile: dict[str, Any], question: str = "", language: str = "tr"
) -> list[dict[str, str]]:
    digest = profile_digest(profile)
    language_instruction = (
        "Türkçe yanıt ver." if language.lower().startswith("tr") else "Answer in English."
    )
    system = f"""You interpret deterministic dataset profiles for a data analyst. {language_instruction}

Hard rules:
- Use ONLY the facts in DATA_PROFILE. Do not recalculate, estimate, invent or infer a benchmark.
- Do not claim causation, business impact, fraud, default risk or anomaly unless a supplied fact proves it.
- Clearly separate observation, interpretation and next-step recommendation.
- Every numeric statement must cite the nearest supplied finding id in square brackets.
- A quality score is a screening heuristic, never an audit opinion.
- If the user's question needs analysis not present in the profile, say which deterministic analysis is needed.
- Do not claim that a file, dashboard or report was created.

Structure the answer as: Basit özet; Veri kalitesi; İş anlamı; Önerilen sonraki analiz."""
    user = {
        "user_question": question.strip() or "Yeni yüklenen veri setinin hızlı profilini yorumla.",
        "data_profile": digest,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str)},
    ]


def verify_interpretation(text: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Check citation syntax without pretending to validate analytical meaning."""
    available = {finding["finding_id"] for finding in profile.get("findings", [])}
    cited = set(_FINDING_CITATION.findall(text))
    valid = sorted(cited & available)
    unknown = sorted(cited - available)
    uncited_numeric_claims: list[str] = []
    for fragment in re.split(r"(?<=[.!?])\s+|\n+", text):
        fragment = fragment.strip()
        if not fragment:
            continue
        without_citations = _FINDING_CITATION.sub("", fragment)
        if _NUMERIC_CLAIM.search(without_citations):
            fragment_valid = set(_FINDING_CITATION.findall(fragment)) & available
            if not fragment_valid:
                uncited_numeric_claims.append(fragment[:300])
    passed = not unknown and not uncited_numeric_claims
    return {
        "status": "passed" if passed else "needs_review",
        "scope": "citation_presence_only",
        "cited_finding_ids": valid,
        "unknown_finding_ids": unknown,
        "uncited_numeric_claims": uncited_numeric_claims[:20],
        "warning": "Bu kontrol yalnızca atıf varlığını doğrular; analitik anlamı doğrulamaz.",
    }


def interpret_profile(
    profile: dict[str, Any],
    question: str = "",
    language: str = "tr",
    model: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    selected_model = validate_local_model_name(
        model or settings.fast_model,
        allow_cloud=settings.allow_cloud_models,
    )
    host = validate_ollama_endpoint(
        settings.ollama_host,
        allow_remote=settings.allow_remote_ollama,
    )
    try:
        from ollama import Client

        client = Client(host=host, timeout=settings.ollama_timeout_seconds)
        request = {
            "model": selected_model,
            "messages": build_interpretation_messages(profile, question, language),
            "options": {
                "temperature": 0.1,
                "num_ctx": min(settings.context_window, 32768),
                "num_predict": min(settings.max_output_tokens, 2048),
            },
        }
        try:
            response = client.chat(**request, think=False)
        except Exception as exc:
            if "think" not in str(exc).lower():
                raise
            response = client.chat(**request)
        text = response.message.content or ""
    except Exception as exc:
        return {
            "status": "unavailable",
            "model": selected_model,
            "message": "Deterministik profil tamamlandı; yerel model yorumu şu anda kullanılamıyor.",
            "reason": str(exc)[:500],
            "available_finding_ids": [
                finding["finding_id"] for finding in profile.get("findings", [])
            ],
        }
    verification = verify_interpretation(text, profile)
    return {
        "status": "completed",
        "model": selected_model,
        "text": text,
        "verification": verification,
        "evidence_finding_ids": verification["cited_finding_ids"],
        "available_finding_ids": [finding["finding_id"] for finding in profile["findings"]],
    }
