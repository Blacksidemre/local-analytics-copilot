from __future__ import annotations

import yaml

from lacopilot.config import get_settings
from lacopilot.security import is_local_or_private_url


def privacy_status() -> dict:
    settings = get_settings()
    ollama_private = is_local_or_private_url(settings.ollama_host)
    profiles = {}
    if settings.database_profiles_path.exists():
        profiles = (
            yaml.safe_load(settings.database_profiles_path.read_text(encoding="utf-8")) or {}
        ).get("profiles", {})
    database_read_only = (
        all(bool(profile.get("read_only", False)) for profile in profiles.values())
        if profiles
        else True
    )
    configured_models = [settings.fast_model, settings.model, settings.deep_model]
    cloud_model_configured = any(model.lower().endswith(":cloud") for model in configured_models)
    local_first = all(
        [
            not settings.allow_web,
            ollama_private,
            not settings.allow_cloud_models,
            not cloud_model_configured,
            database_read_only,
            settings.sql_read_only,
            not settings.allow_network_bind,
        ]
    )
    return {
        "web_enabled": settings.allow_web,
        "ollama_host": settings.ollama_host,
        "ollama_local_or_private": ollama_private,
        "remote_ollama_allowed": settings.allow_remote_ollama,
        "cloud_models_allowed": settings.allow_cloud_models,
        "cloud_model_configured": cloud_model_configured,
        "network_bind_allowed": settings.allow_network_bind,
        "database_profiles_declared_read_only": database_read_only,
        "sql_guard_enabled": settings.sql_read_only,
        "workspace": str(settings.workspace.resolve()),
        "requires_approval_for_writes": settings.require_approval_for_writes,
        "requires_approval_for_external": settings.require_approval_for_external,
        "assessment": "local-first" if local_first else "review_required",
        "notes": [
            "Application guards are not a substitute for OS permissions, firewall/DLP policy, or a read-only DB account.",
            "Web searches and cloud model tags can intentionally send content outside the computer.",
            "A private LAN Ollama host is not the same security boundary as loopback; review network controls.",
        ],
    }
