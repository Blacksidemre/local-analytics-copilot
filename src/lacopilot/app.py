from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from lacopilot import __version__
from lacopilot.actions import ActionStore
from lacopilot.agent_report import create_agent_report
from lacopilot.analysis_history import AnalysisHistoryStore
from lacopilot.analyst_document_reports import (
    create_analyst_html_report,
    create_analyst_pdf_report,
)
from lacopilot.analyst_pipeline import run_analyst_pipeline
from lacopilot.analyst_report import create_analyst_excel_report
from lacopilot.audit import audit
from lacopilot.config import get_settings
from lacopilot.conversations import ConversationStore
from lacopilot.dataset_uploads import save_uploaded_dataset
from lacopilot.hardware import detect_hardware
from lacopilot.ingestion import SUPPORTED_TABLE_EXTENSIONS, IngestionError, source_manifest
from lacopilot.investigate_runtime import build_context_from_profile, run_local_investigation
from lacopilot.knowledge import KnowledgeBase
from lacopilot.llm import OllamaAgent
from lacopilot.memory import LocalMemory
from lacopilot.personality import load_profiles, save_custom_profile
from lacopilot.privacy import privacy_status
from lacopilot.quick_analysis import build_quick_dashboard, interpret_profile
from lacopilot.security import resolve_workspace_path, validate_ollama_endpoint
from lacopilot.tools import TOOL_MAP
from lacopilot.tools.data_tools import profile_dataset

app = FastAPI(title="Local Analytics Copilot", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().parsed_bridge_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-LAC-Token"],
)


@app.middleware("http")
async def optional_api_token(request: Request, call_next):
    s = get_settings()
    if s.api_token and request.url.path.startswith("/api/"):
        supplied = request.headers.get("x-lac-token", "")
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            supplied = auth[7:].strip()
        if not hmac.compare_digest(supplied, s.api_token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing LAC API token"},
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
    )
    return response


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=100_000)
    personality: str | None = Field(default=None, max_length=64)
    model_mode: Literal["fast", "main", "deep"] | None = None
    conversation_id: str | None = Field(default=None, max_length=100)


class AnalyzeRequest(BaseModel):
    file_path: str = Field(min_length=1, max_length=1000)
    sheet_name: str = Field(default="0", max_length=200)


class DatasetProfileRequest(BaseModel):
    file_path: str = Field(min_length=1, max_length=1000)
    sheet_name: str = Field(default="0", max_length=200)


class QuickAnalysisRequest(DatasetProfileRequest):
    question: str = Field(default="", max_length=20_000)
    interpret: bool = True
    language: str = Field(default="tr", max_length=16)
    model: str | None = Field(default=None, max_length=200)


class AnalystAnalysisRequest(DatasetProfileRequest):
    target_column: str = Field(min_length=1, max_length=200)
    target_kind: Literal["binary", "continuous", "categorical"] | None = None
    predictor_columns: list[str] | None = Field(default=None, max_length=50)
    interpret: bool = True
    question: str = Field(default="", max_length=20_000)
    language: str = Field(default="tr", max_length=16)
    model: str | None = Field(default=None, max_length=200)


class AnalystReportRequest(AnalystAnalysisRequest):
    output_name: str = Field(default="analyst_report.xlsx", min_length=1, max_length=200)


class AnalystHtmlReportRequest(AnalystAnalysisRequest):
    output_name: str = Field(default="analyst_report.html", min_length=1, max_length=200)


class AnalystPdfReportRequest(AnalystAnalysisRequest):
    output_name: str = Field(default="analyst_report.pdf", min_length=1, max_length=200)


class AgentAnalysisRequest(DatasetProfileRequest):
    question: str = Field(min_length=1, max_length=4000)
    target_column: str | None = Field(default=None, min_length=1, max_length=200)
    target_kind: Literal["binary", "continuous", "categorical"] | None = None
    predictor_columns: list[str] | None = Field(default=None, max_length=20)
    language: Literal["tr", "en"] = "tr"
    model: str | None = Field(default=None, max_length=200)
    save_history: bool = True


class AgentReportRequest(BaseModel):
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    format: Literal["xlsx", "html", "pdf"]
    output_name: str | None = Field(default=None, min_length=1, max_length=200)


class AnalysisHistoryCompareRequest(BaseModel):
    baseline_run_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    current_run_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class KnowledgeIngestRequest(BaseModel):
    file_path: str = Field(min_length=1, max_length=1000)
    embed_model: str | None = Field(default=None, max_length=200)
    ocr: bool = False


class MemoryDecisionRequest(BaseModel):
    memory_id: int


class PersonalitySaveRequest(BaseModel):
    label: str
    tone: str = "clear, professional"
    teaching_level: int = 7
    technical_depth: int = 6
    directness: int = 7
    explain_method_choice: bool = True
    explain_business_impact: bool = True
    show_formulas: str = "when useful"
    rules: list[str] = Field(default_factory=list, max_length=50)


class LearningUpdateRequest(BaseModel):
    topic: str
    delta: float
    note: str = ""


def _store() -> ConversationStore:
    return ConversationStore(get_settings().conversations_db)


def _analysis_history() -> AnalysisHistoryStore:
    return AnalysisHistoryStore(get_settings().analysis_history_db)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "local-analytics-copilot",
        "version": __version__,
        "data_bridge": {"status": "ready", "api_version": 1},
    }


@app.get("/api/v1/health")
def bridge_health():
    import json
    import urllib.request

    settings = get_settings()
    ollama = {
        "status": "unavailable",
        "models": [],
        "configured_model": settings.model,
        "configured_model_available": False,
    }
    try:
        host = validate_ollama_endpoint(
            settings.ollama_host,
            allow_remote=settings.allow_remote_ollama,
        )
        with urllib.request.urlopen(host + "/api/tags", timeout=2) as r:
            payload = json.load(r)
        models = [
            item.get("name") or item.get("model")
            for item in payload.get("models", [])
            if item.get("name") or item.get("model")
        ]
        ollama = {
            "status": "ready",
            "models": models,
            "configured_model": settings.model,
            "configured_model_available": settings.model in models,
        }
    except Exception as exc:
        ollama["reason"] = str(exc)[:300]
    return {
        "status": "ready" if ollama["status"] == "ready" else "degraded",
        "version": __version__,
        "bridge_api_version": 1,
        "data_bridge": {
            "status": "ready",
            "parser": "lac-deterministic-data-bridge",
            "supported_extensions": sorted(SUPPORTED_TABLE_EXTENSIONS),
        },
        "ollama": ollama,
    }


@app.get("/api/hardware")
def hardware():
    return detect_hardware()


@app.get("/api/tools")
def tools():
    return {"tools": list(TOOL_MAP)}


def _actions() -> ActionStore:
    return ActionStore(get_settings().actions_db)


def _execute_approved(tool_name: str, arguments: dict):
    fn = TOOL_MAP.get(tool_name)
    if not fn or tool_name == "action_status":
        raise PermissionError(f"Onaylanan action için araç bulunamadı: {tool_name}")
    audit(get_settings().logs_dir, "action_execute", tool=tool_name, args=arguments)
    return fn(**arguments)


@app.get("/api/actions")
def action_list(status: str = "pending", limit: int = 100):
    allowed = {"pending", "running", "completed", "rejected", "failed", ""}
    if status not in allowed:
        raise HTTPException(status_code=400, detail="Geçersiz action durumu")
    return {"items": _actions().list(status=status or None, limit=limit)}


@app.get("/api/actions/{action_id}")
def action_get(action_id: str):
    try:
        return _actions().get(action_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Action bulunamadı") from exc


@app.post("/api/actions/{action_id}/approve")
def action_approve(action_id: str):
    try:
        result = _actions().approve_and_execute(action_id, _execute_approved)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit(get_settings().logs_dir, "action_decision", action_id=action_id, status=result["status"])
    return result


@app.post("/api/actions/{action_id}/reject")
def action_reject(action_id: str):
    try:
        result = _actions().reject(action_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit(get_settings().logs_dir, "action_decision", action_id=action_id, status="rejected")
    return result


@app.get("/api/personalities")
def personalities():
    return {"profiles": load_profiles()}


@app.post("/api/personalities/{name}")
def personality_save(name: str, req: PersonalitySaveRequest):
    if not name.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid personality name")
    profile = req.model_dump()
    profile["teaching_level"] = max(0, min(10, int(profile["teaching_level"])))
    profile["technical_depth"] = max(0, min(10, int(profile["technical_depth"])))
    profile["directness"] = max(0, min(10, int(profile["directness"])))
    save_custom_profile(name, profile)
    return {"saved": True, "name": name, "profile": profile}


@app.get("/api/privacy")
def privacy():
    return privacy_status()


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    try:
        return profile_dataset(req.file_path, req.sheet_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _profile_or_http_error(file_path: str, sheet_name: str) -> dict:
    try:
        return profile_dataset(file_path, sheet_name)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict()) from exc
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_dataset", "message": str(exc)},
        ) from exc


@app.post("/api/v1/datasets/profile")
def dataset_profile(req: DatasetProfileRequest):
    profile = _profile_or_http_error(req.file_path, req.sheet_name)
    return {
        "status": "profiled",
        "file_path": req.file_path,
        "selected_sheet": req.sheet_name,
        "profile": profile,
        "dashboard": build_quick_dashboard(profile),
    }


@app.post("/api/v1/datasets/upload", status_code=201)
async def dataset_upload(
    file: UploadFile = File(...),
    sheet_name: str | None = Form(default=None),
    run_profile: bool = Form(default=True),
    interpret: bool = Form(default=False),
    question: str = Form(default=""),
    language: str = Form(default="tr"),
    model: str | None = Form(default=None),
):
    try:
        destination, manifest = await save_uploaded_dataset(file)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict()) from exc
    settings = get_settings()
    relative = str(destination.resolve().relative_to(settings.workspace.resolve()))
    response = {
        "status": "uploaded",
        "file_path": relative,
        "manifest": manifest,
    }
    if manifest["format"] in {"xlsx", "xlsm"} and sheet_name is None:
        nonempty_sheets = [sheet for sheet in manifest["sheets"] if not sheet["empty"]]
        if len(nonempty_sheets) > 1:
            response["status"] = "sheet_selection_required"
            response["sheet_options"] = nonempty_sheets
            return response
        if nonempty_sheets:
            sheet_name = nonempty_sheets[0]["name"]
    selected_sheet = sheet_name or "0"
    if run_profile:
        profile = _profile_or_http_error(relative, selected_sheet)
        response["status"] = "profiled"
        response["selected_sheet"] = selected_sheet
        response["profile"] = profile
        response["dashboard"] = build_quick_dashboard(profile)
        if interpret:
            response["interpretation"] = interpret_profile(
                profile,
                question=question,
                language=language,
                model=model,
            )
    return response


@app.get("/api/v1/datasets/manifest")
def dataset_manifest(file_path: str):
    settings = get_settings()
    try:
        path = resolve_workspace_path(settings.workspace, file_path)
        return source_manifest(path)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict()) from exc
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/analysis/quick")
def quick_analysis(req: QuickAnalysisRequest):
    profile = _profile_or_http_error(req.file_path, req.sheet_name)
    result = {
        "status": "completed",
        "mode": "quick",
        "file_path": req.file_path,
        "profile": profile,
        "dashboard": build_quick_dashboard(profile),
        "interpretation": {"status": "skipped"},
    }
    if req.interpret:
        result["interpretation"] = interpret_profile(
            profile,
            question=req.question,
            language=req.language,
            model=req.model,
        )
    return result


@app.post("/api/v1/analysis/analyst")
def analyst_analysis(req: AnalystAnalysisRequest):
    try:
        return run_analyst_pipeline(
            req.file_path,
            req.target_column,
            sheet_name=req.sheet_name,
            target_kind=req.target_kind,
            predictor_columns=req.predictor_columns,
            interpret=req.interpret,
            question=req.question,
            language=req.language,
            model=req.model,
        )
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict()) from exc
    except (FileNotFoundError, KeyError, PermissionError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_analysis_request", "message": str(exc)},
        ) from exc


@app.post("/api/v1/analysis/agent")
def agent_analysis(req: AgentAnalysisRequest):
    if (req.target_column is None) != (req.target_kind is None):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "incomplete_target_semantics",
                "message": "Hedef analizi için hem hedef sütun hem hedef türü seçilmelidir.",
                "recoverable": True,
            },
        )
    profile = _profile_or_http_error(req.file_path, req.sheet_name)
    try:
        context = build_context_from_profile(
            req.file_path,
            profile,
            sheet_name=req.sheet_name,
            approved_target_columns=[req.target_column] if req.target_column else [],
            approved_target_kinds=(
                {req.target_column: req.target_kind}
                if req.target_column is not None and req.target_kind is not None
                else {}
            ),
            approved_predictor_columns=req.predictor_columns or [],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_agent_context",
                "message": str(exc),
                "recoverable": True,
            },
        ) from exc
    agent = run_local_investigation(
        req.question,
        context,
        language=req.language,
        model=req.model,
    )
    history = {"status": "disabled"}
    if req.save_history:
        try:
            settings = get_settings()
            source_path = resolve_workspace_path(settings.workspace, req.file_path)
            history_id = _analysis_history().record_verified_agent_run(
                dataset_ref=req.file_path,
                source_path=source_path,
                sheet_name=req.sheet_name,
                question=req.question,
                agent=agent,
            )
            history = (
                {"status": "saved", "run_id": history_id}
                if history_id is not None
                else {"status": "not_saved", "reason": "run_not_verified"}
            )
        except (OSError, ValueError):
            history = {"status": "not_saved", "reason": "storage_error"}
    return {
        "schema_version": "agent-api.v1",
        "status": agent["status"],
        "mode": "agent",
        "file_path": req.file_path,
        "selected_sheet": req.sheet_name,
        "dataset": {
            "rows": profile["rows"],
            "columns": profile["columns"],
            "total_missing_cells": profile["total_missing_cells"],
            "missing_cell_pct": profile["missing_cell_pct"],
            "exact_duplicate_copies": profile["duplicate_rows"],
            "schema": profile["schema"],
        },
        "dashboard": build_quick_dashboard(profile),
        "agent": agent,
        "history": history,
    }


@app.get("/api/v1/analysis/history")
def analysis_history(limit: int = 50, dataset_id: str | None = None):
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_history_limit", "message": "limit 1-100 olmalıdır."},
        )
    return {
        "schema_version": "analysis-history-list.v1",
        "runs": _analysis_history().list_runs(limit=limit, dataset_id=dataset_id),
    }


@app.post("/api/v1/analysis/history/compare")
def compare_analysis_history(req: AnalysisHistoryCompareRequest):
    try:
        return _analysis_history().compare_runs(req.baseline_run_id, req.current_run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "history_run_not_found",
                "message": "Karşılaştırılacak analiz kayıtlarından biri bulunamadı.",
                "run_id": str(exc.args[0]),
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_history_comparison",
                "message": str(exc),
                "recoverable": True,
            },
        ) from exc


@app.get("/api/v1/analysis/history/{run_id}")
def analysis_history_run(run_id: str):
    run = _analysis_history().get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "history_run_not_found", "message": "Analiz kaydı bulunamadı."},
        )
    return {"schema_version": "analysis-history.v1", "run": run}


@app.delete("/api/v1/analysis/history/{run_id}")
def delete_analysis_history_run(run_id: str):
    if not _analysis_history().delete_run(run_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "history_run_not_found", "message": "Analiz kaydı bulunamadı."},
        )
    return {"status": "deleted", "run_id": run_id}


@app.post("/api/v1/analysis/agent/report")
def agent_report(req: AgentReportRequest):
    run = _analysis_history().get_run(req.run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "history_run_not_found", "message": "Analiz kaydı bulunamadı."},
        )
    try:
        report = create_agent_report(run, req.format, req.output_name)
        settings = get_settings()
        output = resolve_workspace_path(settings.workspace, report["output"])
        verification = report["verification"]
        return FileResponse(
            output,
            media_type=report["media_type"],
            filename=report["filename"],
            headers={
                "X-LAC-Report-Schema": report["schema_version"],
                "X-LAC-Report-Verification": verification["status"],
                "X-LAC-Report-Findings": str(verification["finding_count"]),
                "X-LAC-Report-Cards": str(verification["dashboard_card_count"]),
            },
        )
    except (KeyError, PermissionError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_agent_report_request", "message": str(exc)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "report_verification_failed", "message": str(exc)},
        ) from exc


def _verified_analyst_report_response(
    req: AnalystAnalysisRequest,
    output_name: str,
    report_factory: Callable[[dict[str, Any], str], dict[str, Any]],
) -> FileResponse:
    try:
        payload = run_analyst_pipeline(
            req.file_path,
            req.target_column,
            sheet_name=req.sheet_name,
            target_kind=req.target_kind,
            predictor_columns=req.predictor_columns,
            interpret=req.interpret,
            question=req.question,
            language=req.language,
            model=req.model,
        )
        report = report_factory(payload, output_name)
        settings = get_settings()
        output = resolve_workspace_path(settings.workspace, report["output"])
        verification = report["verification"]
        return FileResponse(
            output,
            media_type=report["media_type"],
            filename=report["filename"],
            headers={
                "X-LAC-Report-Schema": report["schema_version"],
                "X-LAC-Report-Verification": verification["status"],
                "X-LAC-Report-Findings": str(verification["finding_count"]),
                "X-LAC-Report-Cards": str(verification["dashboard_card_count"]),
            },
        )
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict()) from exc
    except (FileNotFoundError, KeyError, PermissionError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_report_request", "message": str(exc)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "report_verification_failed", "message": str(exc)},
        ) from exc


@app.post("/api/v1/analysis/analyst/report")
def analyst_report(req: AnalystReportRequest):
    return _verified_analyst_report_response(
        req,
        req.output_name,
        create_analyst_excel_report,
    )


@app.post("/api/v1/analysis/analyst/report/html")
def analyst_html_report(req: AnalystHtmlReportRequest):
    return _verified_analyst_report_response(
        req,
        req.output_name,
        create_analyst_html_report,
    )


@app.post("/api/v1/analysis/analyst/report/pdf")
def analyst_pdf_report(req: AnalystPdfReportRequest):
    return _verified_analyst_report_response(
        req,
        req.output_name,
        create_analyst_pdf_report,
    )


@app.post("/api/chat")
def chat(req: ChatRequest):
    cid = req.conversation_id or str(uuid.uuid4())
    store = _store()
    hist = store.history(cid, limit=24)
    try:
        result = OllamaAgent(personality=req.personality, model_mode=req.model_mode).chat(
            req.message, history=hist
        )
        store.append(cid, "user", req.message)
        store.append(
            cid,
            "assistant",
            result["answer"],
            {"model": result.get("model"), "tools": result.get("tool_events", [])},
        )
        return result | {"conversation_id": cid}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/conversations/{conversation_id}")
def clear_conversation(conversation_id: str):
    _store().clear(conversation_id)
    return {"cleared": True, "conversation_id": conversation_id}


@app.post("/api/knowledge/ingest")
def knowledge_ingest(req: KnowledgeIngestRequest):
    try:
        return KnowledgeBase().ingest(req.file_path, embed_model=req.embed_model, ocr=req.ocr)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/knowledge/search")
def knowledge_search(q: str, top_k: int = 5):
    try:
        return {"results": KnowledgeBase().search(q, top_k=top_k)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/memory")
def memory(status: str = "candidate"):
    return {"items": LocalMemory(get_settings().memory_db).list(status=status or None)}


@app.post("/api/memory/approve")
def memory_approve(req: MemoryDecisionRequest):
    LocalMemory(get_settings().memory_db).approve(req.memory_id)
    return {"approved": True, "id": req.memory_id}


@app.post("/api/memory/reject")
def memory_reject(req: MemoryDecisionRequest):
    LocalMemory(get_settings().memory_db).reject(req.memory_id)
    return {"rejected": True, "id": req.memory_id}


@app.get("/api/learning")
def learning_profile():
    return {"items": LocalMemory(get_settings().memory_db).learning_profile()}


@app.post("/api/learning")
def learning_update(req: LearningUpdateRequest):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="Topic boş olamaz")
    delta = max(-25.0, min(25.0, float(req.delta)))
    return LocalMemory(get_settings().memory_db).update_learning(
        req.topic.strip(), delta, req.note[:500]
    )


@app.get("/admin", response_class=HTMLResponse)
def admin():
    return r"""<!doctype html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>LAC Admin</title>
<style>body{font-family:system-ui;max-width:980px;margin:30px auto;padding:0 18px;background:#0b1220;color:#e5e7eb}section{border:1px solid #334155;border-radius:12px;padding:16px;margin:14px 0;background:#0f172a}input,textarea{width:100%;box-sizing:border-box;margin:5px 0;padding:9px;background:#111827;color:#fff;border:1px solid #334155;border-radius:7px}button{padding:9px 13px;background:#1e293b;color:#fff;border:1px solid #475569;border-radius:8px;cursor:pointer}pre{white-space:pre-wrap;background:#111827;padding:12px;border-radius:8px}.row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}@media(max-width:700px){.row{grid-template-columns:1fr}}</style></head><body>
<h1>Local Analytics Copilot — Ayarlar</h1><p><a href='/' style='color:#93c5fd'>← Sohbete dön</a></p>
<section><h2>Tarayıcı API Token</h2><p>Sunucuda <code>LAC_API_TOKEN</code> ayarlıysa aynı değeri burada yalnızca bu tarayıcıda sakla.</p><input id='token' type='password'><button onclick='saveToken()'>Tarayıcıya Kaydet</button></section>
<section><h2>Kişilik Oluştur / Düzenle</h2><input id='pn' value='my_mentor' placeholder='profile key'><input id='label' value='My Mentor' placeholder='Label'><input id='tone' value='clear, patient, professional' placeholder='Tone'><div class='row'><input id='teach' type='number' min='0' max='10' value='9' placeholder='Teaching'><input id='tech' type='number' min='0' max='10' value='5' placeholder='Technical'><input id='direct' type='number' min='0' max='10' value='6' placeholder='Directness'></div><textarea id='rules' rows='4' placeholder='Her satıra bir kural'></textarea><button onclick='saveP()'>Kişiliği Kaydet</button><pre id='pout'></pre></section>
<section><h2>Bilgi Bankasına Dosya Ekle</h2><p>Dosya önce <code>workspace/knowledge</code> altında olmalı.</p><input id='kf' placeholder='knowledge/prosedur.pdf'><input id='em' placeholder='optional embedding model, e.g. embeddinggemma'><button onclick='ingest()'>Ingest</button><pre id='kout'></pre></section>
<section><h2>Onay Bekleyen Hafıza / İş Kuralları</h2><button onclick='loadM()'>Adayları Yükle</button><input id='mid' type='number' placeholder='Memory ID'><button onclick='decide("approve")'>Onayla</button><button onclick='decide("reject")'>Reddet</button><pre id='mout'></pre></section>
<section><h2>Onay Bekleyen İşlemler</h2><p>Dosya üretimi ve dış ağ çağrıları burada, tam araç adı ve argümanlarıyla bekler. İncelemeden onaylama.</p><button onclick='loadA()'>İşlemleri Yükle</button><input id='aid' placeholder='Action ID'><button onclick='actionDecision("approve")'>Onayla ve Çalıştır</button><button onclick='actionDecision("reject")'>Reddet</button><pre id='aout'></pre></section>
<section><h2>Privacy Check</h2><button onclick='privacy()'>Kontrol Et</button><pre id='priv'></pre></section>
<script>
function H(){let t=localStorage.getItem('lac_token')||'';return {'Content-Type':'application/json',...(t?{'X-LAC-Token':t}:{})}}
function saveToken(){localStorage.setItem('lac_token',document.getElementById('token').value);alert('Tarayıcıda saklandı.')}
async function saveP(){let name=pn.value;let body={label:label.value,tone:tone.value,teaching_level:+teach.value,technical_depth:+tech.value,directness:+direct.value,rules:rules.value.split('\n').filter(Boolean)};let r=await fetch('/api/personalities/'+name,{method:'POST',headers:H(),body:JSON.stringify(body)});pout.textContent=JSON.stringify(await r.json(),null,2)}
async function ingest(){let r=await fetch('/api/knowledge/ingest',{method:'POST',headers:H(),body:JSON.stringify({file_path:kf.value,embed_model:em.value||null})});kout.textContent=JSON.stringify(await r.json(),null,2)}
async function loadM(){let r=await fetch('/api/memory?status=candidate',{headers:H()});mout.textContent=JSON.stringify(await r.json(),null,2)}
async function decide(x){let r=await fetch('/api/memory/'+x,{method:'POST',headers:H(),body:JSON.stringify({memory_id:+mid.value})});mout.textContent=JSON.stringify(await r.json(),null,2);loadM()}
async function loadA(){let r=await fetch('/api/actions?status=pending',{headers:H()});aout.textContent=JSON.stringify(await r.json(),null,2)}
async function actionDecision(x){let id=aid.value.trim();if(!id)return;let r=await fetch('/api/actions/'+id+'/'+x,{method:'POST',headers:H()});aout.textContent=JSON.stringify(await r.json(),null,2);loadA()}
async function privacy(){let r=await fetch('/api/privacy',{headers:H()});priv.textContent=JSON.stringify(await r.json(),null,2)}
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return r"""<!doctype html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Local Analytics Copilot</title>
<style>
body{font-family:Inter,system-ui;max-width:1180px;margin:28px auto;padding:0 18px;background:#0b1220;color:#e5e7eb}h1{margin-bottom:4px}.muted{color:#94a3b8}.grid{display:grid;grid-template-columns:1fr 180px 150px;gap:10px}textarea,input,select{width:100%;box-sizing:border-box;padding:12px;background:#111827;color:#fff;border:1px solid #334155;border-radius:9px}button{padding:11px 16px;border:1px solid #475569;background:#1e293b;color:#fff;border-radius:9px;cursor:pointer}button:hover{background:#334155}#chat{background:#0f172a;border:1px solid #25324a;border-radius:12px;min-height:420px;padding:14px;margin-top:14px;overflow:auto}.msg{padding:11px 13px;border-radius:10px;margin:9px 0;white-space:pre-wrap}.u{background:#1e293b}.a{background:#111827;border:1px solid #25324a}.tools{font-size:12px;color:#94a3b8;margin-top:8px}.bar{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}code{color:#93c5fd}@media(max-width:760px){.grid{grid-template-columns:1fr}.bar button{flex:1}}</style></head>
<body><h1>Local Analytics Copilot 1.0 RC1</h1><div class='muted'>Yerel veri analisti + istatistik mentoru + BI/NPL copilot. Ücretli cloud API zorunlu değildir. <a href='/admin' style='color:#93c5fd'>Ayarlar ve onaylar</a></div>
<div class='grid' style='margin-top:16px'><textarea id='msg' rows='3' placeholder="Örn: incoming/portfolio.xlsx dosyasını incele; veri kalitesini değerlendir, uygun analiz planını öğret ve bir Excel dashboard oluştur."></textarea>
<select id='p'><option value='mentor'>Mentor</option><option value='senior_analyst'>Senior Analyst</option><option value='executive'>Executive</option><option value='technical'>Technical</option></select>
<select id='mode'><option value='main'>Main</option><option value='fast'>Fast</option><option value='deep'>Deep</option></select></div>
<div class='bar'><button onclick='send()'>Gönder</button><button onclick='resetChat()'>Yeni Sohbet</button><button onclick='health()'>Sistem Durumu</button></div>
<div id='chat'><div class='msg a'>Hazır. Dosyalarını <code>workspace/incoming</code> altına koy. Şirket dokümanları için <code>workspace/knowledge</code> kullan.</div></div>
<script>
let cid=localStorage.getItem('lac_cid')||crypto.randomUUID(); localStorage.setItem('lac_cid',cid); function H(){let t=localStorage.getItem('lac_token')||'';return {'Content-Type':'application/json',...(t?{'X-LAC-Token':t}:{})}}
function add(cls,text,tools=''){let c=document.getElementById('chat'),d=document.createElement('div');d.className='msg '+cls;d.textContent=text;if(tools){let t=document.createElement('div');t.className='tools';t.textContent=tools;d.appendChild(t)}c.appendChild(d);c.scrollTop=c.scrollHeight}
async function send(){let msg=document.getElementById('msg').value.trim();if(!msg)return;add('u',msg);document.getElementById('msg').value='';add('a','Çalışıyor...');let pending=document.getElementById('chat').lastChild;try{let r=await fetch('/api/chat',{method:'POST',headers:H(),body:JSON.stringify({message:msg,personality:document.getElementById('p').value,model_mode:document.getElementById('mode').value,conversation_id:cid})});let j=await r.json();pending.remove();if(r.ok){let ev=j.tool_events||[];let queued=ev.filter(x=>x.status==='approval_required').length;add('a',j.answer,'Model: '+j.model+' | Tools: '+ev.map(x=>x.tool).join(', ')+(queued?' | Onay bekleyen: '+queued:''));}else add('a',JSON.stringify(j,null,2));}catch(e){pending.remove();add('a','Bağlantı hatası: '+e.message)}}
async function resetChat(){await fetch('/api/conversations/'+cid,{method:'DELETE',headers:H()});cid=crypto.randomUUID();localStorage.setItem('lac_cid',cid);document.getElementById('chat').innerHTML='';add('a','Yeni sohbet başladı.');}
async function health(){let r=await fetch('/health'),j=await r.json();add('a',JSON.stringify(j,null,2));}
document.getElementById('msg').addEventListener('keydown',e=>{if(e.key==='Enter'&&e.ctrlKey)send()});
</script></body></html>"""
