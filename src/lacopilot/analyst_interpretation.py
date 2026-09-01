from __future__ import annotations

import json
import math
import re
from contextlib import suppress
from typing import Any

from lacopilot.config import get_settings
from lacopilot.security import validate_local_model_name, validate_ollama_endpoint

_FINDING_CITATION = re.compile(r"\[(analyst\.[A-Za-z0-9_.-]+)\]")
_NUMERIC_CLAIM = re.compile(r"(?<![\w.])(%\s*)?([+-]?\d+(?:[.,]\d+)*(?:[eE][+-]?\d+)?)(\s*%)?")
_NEGATION = re.compile(
    r"\b(değil\w*|göstermez|kanıtlamaz|çıkarılamaz|belirlenemiyor|verilmedi|"
    r"not|does\s+not|cannot|isn't|aren't|unsupported|unknown)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_CLAIMS = {
    "causal_claim": re.compile(
        r"\b(neden\s+olur|etkiler|yol\s+açar|sürücü(?:dür)?|causes?|drives?|leads\s+to)\b",
        re.IGNORECASE,
    ),
    "business_importance_claim": re.compile(
        r"\b(en\s+önemli|en\s+güçlü|kritik\s+faktör|most\s+important|strongest\s+driver)\b",
        re.IGNORECASE,
    ),
    "unsupported_significance_threshold": re.compile(
        r"\b(istatistiksel(?:\s+olarak)?\s+anlamlı\w*|significant|significance)\b",
        re.IGNORECASE,
    ),
    "unsupported_prediction_semantics": re.compile(
        r"\b(olasılık|tahmin|probability|prediction|predictive)\b",
        re.IGNORECASE,
    ),
    "unsupported_business_semantics": re.compile(
        r"\b(temerrüt\s+riski|riskli\s+müşteri|default\s+risk|fraud\s+risk)\b",
        re.IGNORECASE,
    ),
}


def analyst_digest(payload: dict[str, Any]) -> dict[str, Any]:
    finding_index = {
        finding["finding_id"]: finding
        for finding in payload.get("findings", [])
        if isinstance(finding, dict) and isinstance(finding.get("finding_id"), str)
    }
    selected_effect_ids = [
        card["finding_id"]
        for card in payload.get("dashboard", {}).get("cards", [])
        if isinstance(card, dict) and isinstance(card.get("finding_id"), str)
    ]
    selected_ids: set[str] = set()
    for effect_id in selected_effect_ids:
        base = effect_id.removesuffix(".effect")
        selected_ids.update(
            {
                f"{base}.effect",
                f"{base}.p_value",
                f"{base}.adjusted_p_value",
                f"{base}.n",
            }
        )
    evidence = [
        {
            key: finding[key]
            for key in ("finding_id", "label", "value", "unit", "source", "dimension", "warning")
            if key in finding
        }
        for finding_id, finding in finding_index.items()
        if finding_id in selected_ids
    ]
    analyses = [
        {
            key: analysis[key]
            for key in (
                "analysis_id",
                "target",
                "predictor",
                "predictor_kind",
                "method",
                "effect_name",
                "finding_ids",
                "assumption_status",
                "warning",
            )
            if key in analysis
        }
        for analysis in payload.get("analyses", [])
        if analysis.get("finding_ids", {}).get("effect") in selected_effect_ids
    ]
    return {
        "digest_version": 1,
        "target_semantics": payload.get("target_semantics", {}),
        "kpi_selection": payload.get("kpi_selection", {}),
        "multiple_testing": payload.get("multiple_testing", {}),
        "dashboard_selection": {
            "basis": payload.get("dashboard", {}).get("ranking_basis"),
            "warning": payload.get("dashboard", {}).get("warning"),
        },
        "analyses": analyses,
        "evidence": evidence,
        "rules": [
            "The target was selected explicitly, but its business meaning is unverified.",
            "Adjusted p-values use one Benjamini-Hochberg family over all executed tests.",
            "Methods and effect-size scales can differ; cards are not a cross-method business ranking.",
            "Association does not establish causality or predictive performance.",
        ],
    }


def build_analyst_interpretation_messages(
    payload: dict[str, Any], question: str = "", language: str = "tr"
) -> list[dict[str, str]]:
    language_instruction = (
        "Türkçe yanıt ver." if language.lower().startswith("tr") else "Answer in English."
    )
    system = f"""You explain a deterministic Analyst result. {language_instruction}

Hard rules:
- Use ONLY ANALYST_EVIDENCE. Never recalculate, estimate, combine or invent a number.
- Every numeric statement must cite the exact finding id in square brackets that supplies it.
- Do not call any association causal, predictive, a driver, or business-important.
- Do not claim statistical significance: no approved alpha threshold was supplied.
- The dashboard prioritizes smaller adjusted p-values for screening only. Effect scales from different methods are not directly ranked.
- The target name and binary shape do not establish default, risk, probability, label or any business meaning. State that business meaning is unverified.
- Do not invent a KPI, company rule, benchmark, threshold, report or output file.
- If a requested conclusion is unsupported, state exactly which approved metadata or deterministic analysis is missing.

Structure: Basit özet; Kanıtlı bulgular; Sınırlamalar; Sonraki analiz."""
    user = {
        "user_question": question.strip() or "Hedefle ilişkili kanıtlı bulguları açıkla.",
        "analyst_evidence": analyst_digest(payload),
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
            unsigned = value.lstrip("+-")
            mantissa = re.split(r"[eE]", unsigned, maxsplit=1)[0]
            parts = mantissa.split(separator)
            if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
                with suppress(ValueError):
                    candidates.add(float(value.replace(separator, "")))
    return candidates


def _claim_matches(raw: str, is_percent: bool, finding: dict[str, Any]) -> bool:
    value = finding.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    if is_percent and not str(finding.get("unit", "")).startswith("percent_"):
        return False
    return any(
        math.isclose(candidate, float(value), rel_tol=1e-6, abs_tol=0.011)
        for candidate in _number_candidates(raw)
    )


def _semantic_violations(text: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    columns = {
        str(payload.get("target_semantics", {}).get("column", "")),
        *{str(analysis.get("predictor", "")) for analysis in payload.get("analyses", [])},
    }
    violations: list[dict[str, str]] = []
    for fragment in re.split(r"(?<=[.!?])\s+|\n+", text):
        fragment = fragment.strip()
        if not fragment:
            continue
        semantic_text = _FINDING_CITATION.sub(" ", fragment)
        for column in sorted(columns, key=len, reverse=True):
            if column:
                semantic_text = re.sub(re.escape(column), " ", semantic_text, flags=re.IGNORECASE)
        if _NEGATION.search(semantic_text):
            continue
        for code, pattern in _UNSUPPORTED_CLAIMS.items():
            if pattern.search(semantic_text):
                violations.append({"code": code, "fragment": fragment[:300]})
    return violations[:20]


def verify_analyst_interpretation(text: str, payload: dict[str, Any]) -> dict[str, Any]:
    digest = analyst_digest(payload)
    finding_index = {
        finding["finding_id"]: finding
        for finding in digest["evidence"]
        if isinstance(finding.get("finding_id"), str)
    }
    available = set(finding_index)
    cited = set(_FINDING_CITATION.findall(text))
    valid = sorted(cited & available)
    unknown = sorted(cited - available)
    uncited_numeric_claims: list[str] = []
    numeric_evidence_mismatches: list[dict[str, str]] = []
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
        fragment_ids = set(_FINDING_CITATION.findall(fragment)) & available
        if not fragment_ids:
            uncited_numeric_claims.append(fragment[:300])
            continue
        cited_findings = [finding_index[finding_id] for finding_id in fragment_ids]
        for claim in claims:
            raw = claim.group(2)
            is_percent = bool(claim.group(1) or claim.group(3))
            if not any(_claim_matches(raw, is_percent, finding) for finding in cited_findings):
                numeric_evidence_mismatches.append(
                    {"claim": claim.group(0).strip(), "fragment": fragment[:300]}
                )
    semantic_violations = _semantic_violations(text, payload)
    missing_evidence = not valid
    passed = not (
        missing_evidence
        or unknown
        or uncited_numeric_claims
        or numeric_evidence_mismatches
        or semantic_violations
    )
    return {
        "status": "passed" if passed else "needs_review",
        "scope": "analyst_numeric_evidence_and_semantic_guardrails",
        "cited_finding_ids": valid,
        "unknown_finding_ids": unknown,
        "missing_evidence_citation": missing_evidence,
        "uncited_numeric_claims": uncited_numeric_claims[:20],
        "numeric_evidence_mismatches": numeric_evidence_mismatches[:20],
        "semantic_violations": semantic_violations,
    }


def interpret_analyst_payload(
    payload: dict[str, Any],
    question: str = "",
    language: str = "tr",
    model: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    selected_model = validate_local_model_name(
        model or settings.model,
        allow_cloud=settings.allow_cloud_models,
    )
    host = validate_ollama_endpoint(
        settings.ollama_host,
        allow_remote=settings.allow_remote_ollama,
    )
    available_finding_ids = [
        finding["finding_id"] for finding in analyst_digest(payload)["evidence"]
    ]
    try:
        from ollama import Client

        client = Client(host=host, timeout=settings.ollama_timeout_seconds)
        request = {
            "model": selected_model,
            "messages": build_analyst_interpretation_messages(payload, question, language),
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
            "message": "Deterministik Analyst taraması tamamlandı; yerel model yorumu kullanılamıyor.",
            "reason": str(exc)[:500],
            "available_finding_ids": available_finding_ids,
        }
    verification = verify_analyst_interpretation(text, payload)
    if verification["status"] != "passed":
        return {
            "status": "rejected",
            "model": selected_model,
            "message": "Yerel Analyst yorumu kanıt ve semantik doğrulamasını geçmedi; deterministik bulgular geçerlidir.",
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
