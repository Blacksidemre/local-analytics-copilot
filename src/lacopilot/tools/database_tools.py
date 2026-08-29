from __future__ import annotations

import os

import yaml
from sqlalchemy import create_engine, inspect, text

from lacopilot.audit import audit
from lacopilot.config import get_settings
from lacopilot.security import validate_read_only_sql


def _profiles() -> dict:
    path = get_settings().database_profiles_path
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("profiles", {})


def _engine(profile: str):
    profiles = _profiles()
    if profile not in profiles:
        raise KeyError(f"DB profile bulunamadı: {profile}")
    cfg = profiles[profile]
    settings = get_settings()
    if not settings.sql_read_only or not bool(cfg.get("read_only", False)):
        raise PermissionError(
            "Database araçları yalnızca hem uygulama hem profil read-only olarak ayarlandığında çalışır"
        )
    env = cfg.get("url_env")
    if not env:
        raise ValueError("Database profile url_env tanımlamalı")
    url = os.getenv(env)
    if not url:
        raise RuntimeError(f"{env} environment variable ayarlı değil")
    return create_engine(url, pool_pre_ping=True, future=True), cfg


def database_catalog(profile: str) -> dict:
    """List tables/views and selected columns for a configured read-only database profile."""
    engine, cfg = _engine(profile)
    insp = inspect(engine)
    schemas = cfg.get("schemas") or [None]
    result = []
    for schema in schemas:
        for table in insp.get_table_names(schema=schema):
            cols = insp.get_columns(table, schema=schema)
            result.append(
                {
                    "schema": schema,
                    "table": table,
                    "columns": [
                        {"name": c["name"], "type": str(c["type"]), "nullable": c.get("nullable")}
                        for c in cols[:200]
                    ],
                }
            )
    return {"profile": profile, "objects": result[:500], "read_only_enforced": True}


def database_describe(profile: str, table: str, schema: str | None = None) -> dict:
    engine, _ = _engine(profile)
    insp = inspect(engine)
    cols = insp.get_columns(table, schema=schema)
    pk = insp.get_pk_constraint(table, schema=schema)
    idx = insp.get_indexes(table, schema=schema)
    return {
        "schema": schema,
        "table": table,
        "columns": [
            {"name": c["name"], "type": str(c["type"]), "nullable": c.get("nullable")} for c in cols
        ],
        "primary_key": pk,
        "indexes": idx,
    }


def database_query(profile: str, sql: str, max_rows: int | None = None) -> dict:
    """Execute one read-only SELECT/WITH query with an application-side row cap."""
    s = get_settings()
    engine, cfg = _engine(profile)
    safe = validate_read_only_sql(sql, dialect=cfg.get("dialect"))
    limit = int(max_rows or s.max_query_rows)
    limit = max(1, min(limit, s.max_query_rows, 50_000))
    with engine.connect() as con:
        result = con.execute(text(safe))
        cols = list(result.keys())
        rows = result.fetchmany(limit + 1)
    truncated = len(rows) > limit
    rows = rows[:limit]
    payload = [{c: row._mapping[c] for c in cols} for row in rows]
    audit(
        s.logs_dir,
        "database_query",
        profile=profile,
        sql=safe[:2000],
        rows=len(payload),
        truncated=truncated,
    )
    return {
        "columns": cols,
        "rows": payload,
        "row_count": len(payload),
        "truncated": truncated,
        "guardrail": "Read-only SQL guard is application-side. Use a truly read-only DB account as the primary security boundary.",
    }
