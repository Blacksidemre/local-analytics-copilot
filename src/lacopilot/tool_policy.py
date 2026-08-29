from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

RiskKind = Literal["read", "workspace_write", "external"]


@dataclass(frozen=True)
class ToolRisk:
    kind: RiskKind
    reason: str


def classify_tool_call(tool_name: str, arguments: dict[str, Any]) -> ToolRisk:
    if tool_name == "public_web_search":
        return ToolRisk("external", "Web sorgusu cihaz dışındaki bir arama sağlayıcısına gider.")
    if tool_name in {"generate_synthetic_dataset", "create_pdf_summary", "knowledge_ingest"}:
        return ToolRisk("workspace_write", "Araç workspace içinde kalıcı dosya veya indeks üretir.")
    if tool_name == "dataset_review" and bool(arguments.get("create_dashboard")):
        return ToolRisk("workspace_write", "İnceleme isteği bir Excel dashboard çıktısı üretir.")
    if tool_name == "bi_engine":
        return ToolRisk("workspace_write", "BI motoru Excel/HTML/Pivot çıktısı üretir.")
    if tool_name == "analytics_engine":
        action = str(arguments.get("action", ""))
        if action == "anomaly":
            return ToolRisk("workspace_write", "Anomali analizi işaretli satırları dosyaya yazar.")
    return ToolRisk("read", "Araç yalnızca okur veya geçici hesap yapar.")


def approval_required(tool_name: str, arguments: dict[str, Any], settings: Any) -> ToolRisk | None:
    risk = classify_tool_call(tool_name, arguments)
    if risk.kind == "workspace_write" and settings.require_approval_for_writes:
        return risk
    if risk.kind == "external" and settings.require_approval_for_external:
        return risk
    return None
