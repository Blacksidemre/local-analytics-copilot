from __future__ import annotations

import json
import math
import re
from contextlib import suppress
from typing import Any

from lacopilot.config import get_settings
from lacopilot.security import validate_local_model_name, validate_ollama_endpoint

_FINDING_CITATION = re.compile(r"\[(profile\.[A-Za-z0-9_.-]+)\]")
_NUMERIC_CLAIM = re.compile(r"(?<![\w.])(%\s*)?([+-]?\d+(?:[.,]\d+)*)(\s*%)?")
_QUICK_CARD_FINDING_IDS = (
    "profile.shape.rows",
    "profile.shape.columns",
    "profile.quality.missing_cells",
    "profile.quality.exact_duplicate_copies",
    "profile.quality.score_heuristic",
)
_ROLE_ORDER = ("numeric", "categorical", "datetime", "identifier", "text", "boolean")
_DUPLICATE_REMOVAL_WORDS = re.compile(
    r"\b(kaldır\w*|sil\w*|temizle\w*|çıkar\w*|fazladan|remove\w*|delete\w*|drop\w*|deduplicat\w*|extra\s+cop\w*)\b",
    re.IGNORECASE,
)
_OVERALL_MISSING_WORDS = re.compile(
    r"\b(toplam|genel|veri\s+seti|dataset|overall|total)\b.*\b(eksik|missing)\b|"
    r"\b(eksik|missing)\b.*\b(toplam|genel|veri\s+seti|dataset|overall|total)\b",
    re.IGNORECASE,
)
_BINARY_PREDICTION_SEMANTICS = re.compile(
    r"\b(olasılık|tahmin|probability|prediction)\b",
    re.IGNORECASE,
)
_BINARY_BUSINESS_SEMANTICS = re.compile(
    r"\b(risk|temerrüt|varsayılan|hedef|etiket|default|target|label|means?|represents?|"
    r"indicates?)\b",
    re.IGNORECASE,
)
_SEMANTIC_UNKNOWN = re.compile(
    r"\b(belirlenem\w*|bilinm\w*|çıkarılam\w*|kanıtlanam\w*|unknown|"
    r"cannot\s+(?:be\s+)?determine\w*|not\s+(?:known|mean|imply))\b",
    re.IGNORECASE,
)
_PREDICTION_NEGATION = re.compile(
    r"\b(olasılık|tahmin)\b[^.!?]{0,40}\b(değil\w*|yorumlanamaz|çıkarılamaz)|"
    r"\bnot\s+(?:a\s+)?(probability|prediction)\b|"
    r"\b(probability|prediction)\b[^.!?]{0,40}\bnot\s+supported\b",
    re.IGNORECASE,
)


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
    missing_pct_finding_ids = {
        finding.get("dimension", {}).get("column"): finding["finding_id"]
        for finding in profile.get("findings", [])
        if finding.get("finding_id", "").startswith("profile.quality.missing_pct.column.")
    }
    missing_by_column = sorted(
        (
            {
                "finding_id": missing_finding_ids[column],
                "pct_finding_id": missing_pct_finding_ids[column],
                "column": column,
                "count": int(count),
                "pct": float(profile.get("missing_pct", {}).get(column, 0.0)),
            }
            for column, count in profile.get("missing_count", {}).items()
            if int(count) > 0
            and column in missing_finding_ids
            and column in missing_pct_finding_ids
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


def _binary_column_facts(profile: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "column": item["name"],
            "classification": "binary_observed_values",
            "technical_role": item.get("role", "unknown"),
            "business_meaning": "unknown_without_approved_metadata",
            "probability_interpretation_supported": False,
        }
        for item in profile.get("schema", [])
        if item.get("unique") == 2
    ]


def profile_digest(profile: dict[str, Any]) -> dict[str, Any]:
    evidence = [
        {
            key: finding[key]
            for key in ("finding_id", "label", "value", "unit", "source", "dimension", "warning")
            if key in finding
        }
        for finding in profile.get("findings", [])
        if isinstance(finding, dict)
        and isinstance(finding.get("finding_id"), str)
        and isinstance(finding.get("value"), (int, float))
        and not isinstance(finding.get("value"), bool)
    ]
    ingestion = profile.get("ingestion", {})
    return {
        "profile_digest_version": 2,
        "evidence": evidence,
        "duplicate_semantics": {
            "removable_extra_copy_finding_id": "profile.quality.exact_duplicate_copies",
            "group_rows_including_originals_finding_id": "profile.quality.duplicate_group_rows",
            "rule": "For deduplication, only the extra-copy finding is a potential removal count. The group-row finding includes retained originals and is never a removal count.",
        },
        "missing_semantics": {
            "dataset_rate_finding_id": "profile.quality.missing_cell_rate",
            "rule": "Column missing percentages have separate denominators. Never add them; use only the dataset-rate finding for an overall missing rate.",
        },
        "binary_columns": _binary_column_facts(profile),
        "business_semantics_rule": "Column names and binary shape do not prove target, probability, risk or business meaning. Without approved metadata, state that the meaning cannot be determined.",
        "constant_columns": profile["constant_columns"],
        "ingestion": {
            key: ingestion[key]
            for key in ("format", "source_name", "parser", "parser_version")
            if key in ingestion
        },
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
- Use ONLY the supplied evidence entries in DATA_PROFILE. Do not recalculate, estimate, add, average or infer any number.
- Do not claim causation, business impact, fraud, default risk or anomaly unless a supplied fact proves it.
- Clearly separate observation, interpretation and next-step recommendation.
- Every numeric statement must cite the exact evidence finding id that supplies that number in square brackets. One citation does not support other numbers.
- exact_duplicate_copies is the extra-copy count. duplicate_group_rows includes retained originals and MUST NOT be recommended as a removal count.
- NEVER add column-level missing percentages. For the dataset-wide missing rate, use only profile.quality.missing_cell_rate.
- A binary column is not a probability or prediction. Do not infer target, label, risk or business meaning from a column name. If approved meaning is absent, explicitly say "belirlenemiyor".
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


def _number_candidates(raw: str) -> set[float]:
    value = raw.replace(" ", "")
    candidates: set[float] = set()
    with suppress(ValueError):
        candidates.add(float(value.replace(",", ".")))
    if "." in value and "," in value:
        decimal = "," if value.rfind(",") > value.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        with suppress(ValueError):
            candidates.add(float(value.replace(thousands, "").replace(decimal, ".")))
    else:
        separator = "," if "," in value else "." if "." in value else ""
        if separator:
            parts = value.lstrip("+-").split(separator)
            if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
                with suppress(ValueError):
                    candidates.add(float(value.replace(separator, "")))
    return candidates


def _claim_matches_finding(raw: str, is_percent: bool, finding: dict[str, Any]) -> bool:
    value = finding.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    if is_percent and not str(finding.get("unit", "")).startswith("percent_"):
        return False
    return any(
        math.isclose(candidate, float(value), rel_tol=1e-6, abs_tol=0.011)
        for candidate in _number_candidates(raw)
    )


def _semantic_violations(text: str, profile: dict[str, Any]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for fragment in re.split(r"(?<=[.!?])\s+|\n+", text):
        fragment = fragment.strip()
        if not fragment:
            continue
        cited = set(_FINDING_CITATION.findall(fragment))
        if "profile.quality.duplicate_group_rows" in cited and _DUPLICATE_REMOVAL_WORDS.search(
            fragment
        ):
            violations.append(
                {
                    "code": "duplicate_group_rows_used_as_removal_count",
                    "fragment": fragment[:300],
                }
            )
        column_pct_citations = {
            finding_id
            for finding_id in cited
            if finding_id.startswith("profile.quality.missing_pct.column.")
        }
        if (
            len(column_pct_citations) >= 2
            and _OVERALL_MISSING_WORDS.search(fragment)
            and "profile.quality.missing_cell_rate" not in cited
        ):
            violations.append(
                {
                    "code": "column_missing_percentages_used_as_overall_rate",
                    "fragment": fragment[:300],
                }
            )
        for item in _binary_column_facts(profile):
            column = str(item["column"])
            if column.casefold() not in fragment.casefold():
                continue
            without_column = re.sub(re.escape(column), " ", fragment, flags=re.IGNORECASE)
            meaning_unknown = bool(_SEMANTIC_UNKNOWN.search(without_column))
            unsupported_business = bool(_BINARY_BUSINESS_SEMANTICS.search(without_column))
            unsupported_prediction = bool(
                _BINARY_PREDICTION_SEMANTICS.search(without_column)
                and not _PREDICTION_NEGATION.search(without_column)
            )
            if not meaning_unknown and (unsupported_business or unsupported_prediction):
                violations.append(
                    {
                        "code": "unsupported_binary_business_semantics",
                        "fragment": fragment[:300],
                    }
                )
    return violations[:20]


def verify_interpretation(text: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Verify numeric evidence binding and high-risk profile semantics."""
    finding_index = {
        finding["finding_id"]: finding
        for finding in profile.get("findings", [])
        if isinstance(finding, dict) and isinstance(finding.get("finding_id"), str)
    }
    available = set(finding_index)
    cited = set(_FINDING_CITATION.findall(text))
    valid = sorted(cited & available)
    unknown = sorted(cited - available)
    uncited_numeric_claims: list[str] = []
    numeric_evidence_mismatches: list[dict[str, Any]] = []
    for fragment in re.split(r"(?<=[.!?])\s+|\n+", text):
        fragment = fragment.strip()
        if not fragment:
            continue
        without_citations = _FINDING_CITATION.sub("", fragment)
        without_citations = re.sub(
            r"^\s*(?:#{1,6}\s*)?(?:\d+[.)]\s+|[-*]\s+)", "", without_citations
        )
        claims = list(_NUMERIC_CLAIM.finditer(without_citations))
        if not claims:
            continue
        fragment_valid = set(_FINDING_CITATION.findall(fragment)) & available
        if not fragment_valid:
            uncited_numeric_claims.append(fragment[:300])
            continue
        cited_findings = [finding_index[finding_id] for finding_id in fragment_valid]
        for claim in claims:
            raw = claim.group(2)
            is_percent = bool(claim.group(1) or claim.group(3))
            if not any(_claim_matches_finding(raw, is_percent, item) for item in cited_findings):
                numeric_evidence_mismatches.append(
                    {"claim": claim.group(0).strip(), "fragment": fragment[:300]}
                )
    semantic_violations = _semantic_violations(text, profile)
    passed = not (
        unknown or uncited_numeric_claims or numeric_evidence_mismatches or semantic_violations
    )
    return {
        "status": "passed" if passed else "needs_review",
        "scope": "numeric_evidence_and_semantic_guardrails",
        "cited_finding_ids": valid,
        "unknown_finding_ids": unknown,
        "uncited_numeric_claims": uncited_numeric_claims[:20],
        "numeric_evidence_mismatches": numeric_evidence_mismatches[:20],
        "semantic_violations": semantic_violations,
        "warning": "Bu kontrol kanıt bağını ve yüksek riskli profil semantiğini doğrular; genel iş doğruluğu için onaylı metadata gerekir.",
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
    available_finding_ids = [finding["finding_id"] for finding in profile["findings"]]
    if verification["status"] != "passed":
        return {
            "status": "rejected",
            "model": selected_model,
            "message": "Yerel model yorumu kanıt ve semantik doğrulamasını geçmedi; deterministik dashboard sonuçları geçerlidir.",
            "verification": verification,
            "evidence_finding_ids": verification["cited_finding_ids"],
            "available_finding_ids": available_finding_ids,
        }
    return {
        "status": "completed",
        "model": selected_model,
        "text": text,
        "verification": verification,
        "evidence_finding_ids": verification["cited_finding_ids"],
        "available_finding_ids": available_finding_ids,
    }
