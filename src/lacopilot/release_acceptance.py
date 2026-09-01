from __future__ import annotations

import argparse
import json
import math
import os
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

AgentMode = Literal["auto", "offline", "live"]

EXPECTED_PROFILE = {
    "rows": 1508,
    "columns": 22,
    "total_missing_cells": 52,
    "duplicate_rows": 8,
    "missing_count": {
        "monthly_income_try": 24,
        "employment_years": 16,
        "payment_ratio_3m": 12,
    },
}
PREDICTORS = ["utilization_rate", "customer_segment", "legal_status"]
FORBIDDEN_PAYLOAD_KEYS = {"raw_rows", "records", "sample_rows", "model_prompt"}


class AcceptanceFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise AcceptanceFailure(code, message)


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        if set(value) & FORBIDDEN_PAYLOAD_KEYS:
            return True
        return any(_contains_forbidden_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _numeric_findings(payload: dict[str, Any]) -> dict[str, float]:
    findings: dict[str, float] = {}
    for finding in payload.get("findings", []):
        finding_id = finding.get("finding_id")
        value = finding.get("value")
        _require(
            isinstance(finding_id, str) and finding_id,
            "invalid_finding_id",
            "Analyst finding_id sözleşmesi geçersiz.",
        )
        _require(
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(float(value)),
            "invalid_finding_value",
            f"{finding_id} finite deterministik sayı taşımıyor.",
        )
        _require(
            isinstance(finding.get("source"), str) and bool(finding["source"]),
            "missing_finding_source",
            f"{finding_id} deterministik kaynak taşımıyor.",
        )
        _require(
            finding_id not in findings,
            "duplicate_finding_id",
            f"Tekrarlayan finding_id: {finding_id}",
        )
        findings[finding_id] = float(value)
    _require(bool(findings), "missing_findings", "Analyst finding manifesti boş.")
    return findings


def _assert_findings_equal(
    baseline: dict[str, float], current: dict[str, float], *, label: str
) -> None:
    _require(
        baseline.keys() == current.keys(),
        "finding_id_parity_failed",
        f"{label} finding_id kümeleri eşleşmiyor.",
    )
    for finding_id, baseline_value in baseline.items():
        _require(
            math.isclose(baseline_value, current[finding_id], rel_tol=1e-12, abs_tol=1e-12),
            "finding_value_parity_failed",
            f"{label} değeri eşleşmiyor: {finding_id}",
        )


def _response_json(response: Any, check_id: str) -> dict[str, Any]:
    if response.status_code != 200:
        detail_code = "unknown"
        try:
            detail = response.json().get("detail", {})
            if isinstance(detail, dict):
                detail_code = str(detail.get("code", "unknown"))[:100]
        except (TypeError, ValueError):
            pass
        raise AcceptanceFailure(
            f"{check_id}_http_{response.status_code}_{detail_code}",
            f"{check_id} API kontrolü HTTP {response.status_code} döndürdü.",
        )
    payload = response.json()
    _require(isinstance(payload, dict), f"{check_id}_invalid_json", "API yanıtı nesne değil.")
    return payload


def _add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    status: Literal["passed", "skipped", "failed"],
    summary: str,
    **bounded_details: Any,
) -> None:
    check = {"id": check_id, "status": status, "summary": summary}
    if bounded_details:
        check["details"] = bounded_details
    checks.append(check)


@contextmanager
def _acceptance_environment(run_root: Path, agent_mode: AgentMode, model: str | None):
    keys = {
        "LAC_WORKSPACE",
        "LAC_CONFIG_DIR",
        "LAC_API_TOKEN",
        "LAC_ALLOW_WEB",
        "LAC_ALLOW_CLOUD_MODELS",
        "LAC_ALLOW_REMOTE_OLLAMA",
        "LAC_OLLAMA_HOST",
        "LAC_MODEL",
    }
    previous = {key: os.environ.get(key) for key in keys}
    os.environ.update(
        {
            "LAC_WORKSPACE": str(run_root / "workspace"),
            "LAC_CONFIG_DIR": str(run_root / "config"),
            "LAC_API_TOKEN": "",
            "LAC_ALLOW_WEB": "false",
            "LAC_ALLOW_CLOUD_MODELS": "false",
            "LAC_ALLOW_REMOTE_OLLAMA": "false",
        }
    )
    if agent_mode == "offline":
        os.environ["LAC_OLLAMA_HOST"] = "http://127.0.0.1:9"
    if model:
        os.environ["LAC_MODEL"] = model
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        from lacopilot.config import get_settings

        get_settings.cache_clear()


def _default_run_root() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path.cwd() / "workspace" / "acceptance-runs" / f"{stamp}-{uuid.uuid4().hex[:8]}"


def run_release_acceptance(
    *,
    run_root: Path | None = None,
    agent_mode: AgentMode = "auto",
    model: str | None = None,
) -> dict[str, Any]:
    started = datetime.now(UTC)
    started_clock = time.monotonic()
    root = (run_root or _default_run_root()).resolve()
    root.mkdir(parents=True, exist_ok=False)
    result_path = root / "acceptance-result.json"
    checks: list[dict[str, Any]] = []
    artifacts: list[str] = []
    executed_agent_mode = "not_started"
    failure: dict[str, str] | None = None

    try:
        with _acceptance_environment(root, agent_mode, model):
            from fastapi.testclient import TestClient

            from lacopilot.agent_report import create_agent_report
            from lacopilot.analysis_history import AnalysisHistoryStore
            from lacopilot.analyst_document_reports import (
                create_analyst_html_report,
                create_analyst_pdf_report,
            )
            from lacopilot.analyst_report import create_analyst_excel_report
            from lacopilot.app import app
            from lacopilot.config import get_settings
            from lacopilot.regression_fixture import write_credit_risk_regression_fixture

            get_settings.cache_clear()
            settings = get_settings()
            _require(
                not settings.allow_web
                and not settings.allow_cloud_models
                and not settings.allow_remote_ollama,
                "unsafe_acceptance_configuration",
                "Acceptance yalnız local-first güvenlik ayarlarıyla çalışır.",
            )
            _add_check(
                checks,
                "local_privacy_configuration",
                "passed",
                "Web, cloud model ve remote Ollama kapalı.",
            )

            client = TestClient(app)
            health = _response_json(client.get("/api/v1/health"), "health")
            _require(
                health.get("data_bridge", {}).get("status") == "ready",
                "data_bridge_not_ready",
                "Deterministik Data Bridge hazır değil.",
            )
            _add_check(checks, "data_bridge_health", "passed", "Data Bridge hazır.")

            paths = write_credit_risk_regression_fixture(settings.incoming_dir)
            artifacts.extend(
                str(path.relative_to(settings.workspace)).replace("\\", "/")
                for path in paths.values()
            )
            quick_payloads: dict[str, dict[str, Any]] = {}
            analyst_payloads: dict[str, dict[str, Any]] = {}
            analyst_findings: dict[str, dict[str, float]] = {}

            for file_format, path in paths.items():
                dataset_ref = f"incoming/{path.name}"
                quick = _response_json(
                    client.post(
                        "/api/v1/analysis/quick",
                        json={
                            "file_path": dataset_ref,
                            "sheet_name": "0",
                            "interpret": False,
                        },
                    ),
                    f"quick_{file_format}",
                )
                profile = quick.get("profile", {})
                for key in ("rows", "columns", "total_missing_cells", "duplicate_rows"):
                    _require(
                        profile.get(key) == EXPECTED_PROFILE[key],
                        f"quick_{file_format}_{key}_mismatch",
                        f"{file_format.upper()} {key} beklenen değeri taşımıyor.",
                    )
                for column, expected in EXPECTED_PROFILE["missing_count"].items():
                    _require(
                        profile.get("missing_count", {}).get(column) == expected,
                        f"quick_{file_format}_missing_mismatch",
                        f"{file_format.upper()} {column} missing sayısı yanlış.",
                    )
                cards = quick.get("dashboard", {}).get("cards", [])
                _require(
                    bool(cards)
                    and all(card.get("finding_id") and card.get("source") for card in cards),
                    f"quick_{file_format}_dashboard_unbound",
                    f"{file_format.upper()} Quick Dashboard finding zinciri geçersiz.",
                )
                _require(
                    not _contains_forbidden_key(quick),
                    f"quick_{file_format}_raw_data_exposure",
                    "Quick API bounded sözleşme dışı ham veri taşıyor.",
                )
                quick_payloads[file_format] = quick

                analyst = _response_json(
                    client.post(
                        "/api/v1/analysis/analyst",
                        json={
                            "file_path": dataset_ref,
                            "sheet_name": "0",
                            "target_column": "default_next_30d",
                            "target_kind": "binary",
                            "predictor_columns": PREDICTORS,
                            "interpret": False,
                        },
                    ),
                    f"analyst_{file_format}",
                )
                _require(
                    analyst.get("verification", {}).get("status") == "passed",
                    f"analyst_{file_format}_verification_failed",
                    f"{file_format.upper()} Analyst verifier geçmedi.",
                )
                semantics = analyst.get("target_semantics", {})
                _require(
                    semantics.get("statistical_role") == "binary"
                    and semantics.get("business_meaning_status") == "unverified"
                    and semantics.get("business_meaning") is None,
                    f"analyst_{file_format}_target_semantics_failed",
                    "Binary hedefe kanıtsız iş anlamı eklendi.",
                )
                _require(
                    not _contains_forbidden_key(analyst),
                    f"analyst_{file_format}_raw_data_exposure",
                    "Analyst API bounded sözleşme dışı ham veri taşıyor.",
                )
                analyst_payloads[file_format] = analyst
                analyst_findings[file_format] = _numeric_findings(analyst)

            csv_profile = quick_payloads["csv"]["profile"]
            xlsx_profile = quick_payloads["xlsx"]["profile"]
            _require(
                {
                    key: csv_profile[key]
                    for key in ("rows", "columns", "total_missing_cells", "duplicate_rows")
                }
                == {
                    key: xlsx_profile[key]
                    for key in ("rows", "columns", "total_missing_cells", "duplicate_rows")
                },
                "quick_csv_xlsx_parity_failed",
                "CSV/XLSX Quick profil sözleşmeleri eşleşmiyor.",
            )
            _assert_findings_equal(
                analyst_findings["csv"],
                analyst_findings["xlsx"],
                label="CSV/XLSX Analyst",
            )
            _add_check(
                checks,
                "csv_xlsx_quick_analyst_parity",
                "passed",
                "CSV/XLSX profil ve deterministik Analyst finding değerleri eşleşiyor.",
                rows=EXPECTED_PROFILE["rows"],
                columns=EXPECTED_PROFILE["columns"],
                missing_cells=EXPECTED_PROFILE["total_missing_cells"],
                duplicate_copies=EXPECTED_PROFILE["duplicate_rows"],
                analyst_findings=len(analyst_findings["csv"]),
            )

            analyst = analyst_payloads["csv"]
            reports = [
                create_analyst_excel_report(analyst, "acceptance_analyst.xlsx"),
                create_analyst_html_report(analyst, "acceptance_analyst.html"),
                create_analyst_pdf_report(analyst, "acceptance_analyst.pdf"),
            ]
            _require(
                all(report["verification"]["status"] == "passed" for report in reports),
                "analyst_report_verification_failed",
                "Analyst raporlarından biri doğrulamayı geçmedi.",
            )
            report_digests = {report["verification"]["manifest_sha256"] for report in reports}
            _require(
                len(report_digests) == 1,
                "analyst_report_manifest_mismatch",
                "Excel/HTML/PDF aynı Analyst evidence manifestine bağlı değil.",
            )
            artifacts.extend(report["output"] for report in reports)
            _add_check(
                checks,
                "analyst_reports",
                "passed",
                "Excel, HTML ve PDF aynı doğrulanmış evidence manifestini kullanıyor.",
                formats=["xlsx", "html", "pdf"],
                manifest_sha256=next(iter(report_digests)),
            )

            ollama = health.get("ollama", {})
            live_available = (
                ollama.get("status") == "ready" and ollama.get("configured_model_available") is True
            )
            if agent_mode == "live" and not live_available:
                raise AcceptanceFailure(
                    "live_ollama_model_unavailable",
                    "Live Agent kabulü için Ollama ve seçili yerel model hazır olmalıdır.",
                )
            run_live = agent_mode == "live" or (agent_mode == "auto" and live_available)
            executed_agent_mode = "live" if run_live else "deterministic_fallback"
            if run_live:
                _add_check(
                    checks,
                    "ollama_preflight",
                    "passed",
                    "Ollama ve seçili yerel model hazır.",
                    configured_model=ollama.get("configured_model"),
                )
            else:
                _add_check(
                    checks,
                    "ollama_preflight",
                    "skipped" if agent_mode == "auto" else "passed",
                    (
                        "Ollama/model bulunamadı; güvenli deterministic fallback sınanıyor."
                        if agent_mode == "auto"
                        else "Offline modda deterministic fallback bilerek zorlandı."
                    ),
                )

            agent_runs: list[dict[str, Any]] = []
            for file_format, path in paths.items():
                response = _response_json(
                    client.post(
                        "/api/v1/analysis/agent",
                        json={
                            "file_path": f"incoming/{path.name}",
                            "sheet_name": "0",
                            "question": (
                                "Bu veri setini özetle, veri kalitesi sorunlarını bul ve yalnız "
                                "doğrulanmış deterministik bulguları açıkla."
                            ),
                            "save_history": True,
                        },
                    ),
                    f"agent_{file_format}",
                )
                _require(
                    not _contains_forbidden_key(response),
                    f"agent_{file_format}_raw_data_exposure",
                    "Agent API bounded sözleşme dışı ham veri taşıyor.",
                )
                dataset = response.get("dataset", {})
                _require(
                    dataset.get("rows") == EXPECTED_PROFILE["rows"]
                    and dataset.get("columns") == EXPECTED_PROFILE["columns"]
                    and dataset.get("total_missing_cells")
                    == EXPECTED_PROFILE["total_missing_cells"]
                    and dataset.get("exact_duplicate_copies") == EXPECTED_PROFILE["duplicate_rows"],
                    f"agent_{file_format}_dataset_contract_failed",
                    f"{file_format.upper()} Agent dataset özeti deterministik profile bağlı değil.",
                )
                if run_live:
                    agent = response.get("agent", {})
                    _require(
                        response.get("status") == "completed"
                        and agent.get("run", {}).get("verification", {}).get("status") == "passed",
                        f"agent_{file_format}_verifier_failed",
                        f"{file_format.upper()} live Agent verifier geçmedi.",
                    )
                    _require(
                        agent.get("synthesis", {}).get("status") == "completed"
                        and agent.get("synthesis", {}).get("verification", {}).get("status")
                        == "passed",
                        f"agent_{file_format}_synthesis_failed",
                        f"{file_format.upper()} live Agent sentezi evidence doğrulamasını geçmedi.",
                    )
                    _require(
                        response.get("history", {}).get("status") == "saved",
                        f"agent_{file_format}_history_not_saved",
                        "Verifier-passed Agent run history'ye kaydedilmedi.",
                    )
                    agent_runs.append(response)
                else:
                    _require(
                        response.get("status") == "planner_unavailable"
                        and response.get("history")
                        == {"status": "not_saved", "reason": "run_not_verified"}
                        and bool(response.get("dashboard", {}).get("cards")),
                        f"agent_{file_format}_fallback_failed",
                        "Model yokken deterministic dashboard fallback sözleşmesi korunmadı.",
                    )

            if run_live:
                _add_check(
                    checks,
                    "live_agent_csv_xlsx",
                    "passed",
                    "CSV/XLSX planner, executor, verifier, synthesis ve history zinciri geçti.",
                )
                run_id = agent_runs[0]["history"]["run_id"]
                archived = AnalysisHistoryStore(settings.analysis_history_db).get_run(run_id)
                _require(
                    archived is not None and archived.get("verifier_status") == "passed",
                    "agent_history_manifest_invalid",
                    "Kaydedilen Agent evidence manifesti açılamadı.",
                )
                agent_reports = [
                    create_agent_report(archived, report_format)
                    for report_format in ("xlsx", "html", "pdf")
                ]
                _require(
                    all(report["verification"]["status"] == "passed" for report in agent_reports),
                    "agent_report_verification_failed",
                    "Agent raporlarından biri doğrulamayı geçmedi.",
                )
                agent_digests = {
                    report["verification"]["manifest_sha256"] for report in agent_reports
                }
                _require(
                    len(agent_digests) == 1,
                    "agent_report_manifest_mismatch",
                    "Agent Excel/HTML/PDF evidence manifestleri eşleşmiyor.",
                )
                artifacts.extend(report["output"] for report in agent_reports)
                _add_check(
                    checks,
                    "agent_reports",
                    "passed",
                    "Agent Excel, HTML ve PDF aynı verifier-passed manifesti kullanıyor.",
                    manifest_sha256=next(iter(agent_digests)),
                )
            else:
                _add_check(
                    checks,
                    "model_unavailable_fallback",
                    "passed",
                    "Model yokken Quick/Analyst ve Agent deterministic dashboard kullanılabilir kaldı.",
                )
                _add_check(
                    checks,
                    "live_agent_csv_xlsx",
                    "skipped",
                    "Canlı Ollama/model olmadan Agent planner+synthesis kabulü çalıştırılmadı.",
                )

    except AcceptanceFailure as exc:
        failure = {"code": exc.code, "message": str(exc)}
        _add_check(checks, exc.code, "failed", str(exc))
    except Exception as exc:  # fail closed without leaking environment details
        failure = {
            "code": "unexpected_acceptance_error",
            "message": f"Beklenmeyen güvenli kabul hatası: {type(exc).__name__}",
        }
        _add_check(
            checks,
            "unexpected_acceptance_error",
            "failed",
            failure["message"],
        )

    completed = datetime.now(UTC)
    has_failed = any(check["status"] == "failed" for check in checks)
    has_skipped = any(check["status"] == "skipped" for check in checks)
    status = "failed" if has_failed else ("passed_with_skips" if has_skipped else "passed")
    result: dict[str, Any] = {
        "schema_version": "release-acceptance.v1",
        "status": status,
        "agent_mode_requested": agent_mode,
        "agent_mode_executed": executed_agent_mode,
        "started_at": started.isoformat(),
        "completed_at": completed.isoformat(),
        "duration_seconds": round(time.monotonic() - started_clock, 3),
        "run_root": str(root),
        "checks": checks,
        "artifacts": sorted(set(artifacts)),
        "limitations": [
            "Bu harness native Tauri pencere/installer etkileşimini doğrulamaz.",
            "Fiziksel Windows launch, shortcut, upgrade ve uninstall ayrıca kabul edilmelidir.",
        ],
    }
    if failure is not None:
        result["failure"] = failure
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local Analytics Copilot pre-release acceptance harness"
    )
    parser.add_argument(
        "--agent-mode",
        choices=("auto", "offline", "live"),
        default="auto",
        help="auto: live model varsa kullan; offline: fallback; live: Ollama/model zorunlu",
    )
    parser.add_argument("--model", help="Live Agent için açık Ollama model adı")
    parser.add_argument("--run-root", type=Path, help="İzole acceptance artifact dizini")
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = run_release_acceptance(
        run_root=args.run_root,
        agent_mode=args.agent_mode,
        model=args.model,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result["status"] == "failed" else 0)


if __name__ == "__main__":
    main()
