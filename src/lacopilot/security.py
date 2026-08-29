from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from urllib.parse import urlparse

from sqlglot import exp, parse
from sqlglot.errors import ParseError

PII_PATTERNS = [
    re.compile(r"\b\d{11}\b"),
    re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I),
    re.compile(r"\b(?:\+?90\s?)?(?:0?5\d{2})[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b"),
]
SECRET_PATTERNS = [
    re.compile(r"\b(?:api[_ -]?key|access[_ -]?token|password|parola|secret)\s*[:=]", re.I),
    re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{16,}\b"),
]
_EXTERNAL_DATA_FUNCTION = re.compile(
    r"\b(?:read_csv|read_json|read_parquet|read_text|glob|httpfs|sqlite_scan|postgres_scan|"
    r"mysql_scan|iceberg_scan|delta_scan|st_read|shell|system)\w*\s*\(",
    re.I,
)


def resolve_workspace_path(workspace: Path, value: str | Path) -> Path:
    workspace = workspace.resolve()
    raw = Path(value)
    path = raw.resolve() if raw.is_absolute() else (workspace / raw).resolve()
    try:
        path.relative_to(workspace)
    except ValueError as exc:
        raise PermissionError(f"Path workspace dışına çıkıyor: {path}") from exc
    return path


def validate_file_size(path: Path, max_mb: int) -> Path:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path)
    size = path.stat().st_size
    limit = int(max_mb) * 1024 * 1024
    if size > limit:
        raise PermissionError(
            f"Dosya boyutu izin verilen {max_mb} MB sınırını aşıyor: {size / 1024**2:.1f} MB"
        )
    return path


def _parse_single_select(sql: str, dialect: str | None = None) -> exp.Expression:
    stripped = sql.strip().rstrip(";")
    if not stripped:
        raise ValueError("SQL boş olamaz")
    try:
        statements = parse(stripped, read=dialect)
    except (ParseError, ValueError) as exc:
        raise ValueError(f"SQL ayrıştırılamadı: {exc}") from exc
    if len(statements) != 1:
        raise PermissionError("Tek seferde yalnızca bir SQL ifadesi çalıştırılabilir")
    statement = statements[0]
    if not isinstance(statement, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise PermissionError("Yalnızca SELECT/WITH sorguları izinli")

    blocked_names = (
        "Insert",
        "Update",
        "Delete",
        "Drop",
        "Alter",
        "Create",
        "Merge",
        "Command",
        "Copy",
        "Transaction",
        "Grant",
        "Revoke",
        "Use",
        "Lock",
        "Into",
    )
    blocked_types = tuple(
        expression_type
        for name in blocked_names
        if (expression_type := getattr(exp, name, None)) is not None
    )
    if blocked_types and any(isinstance(node, blocked_types) for node in statement.walk()):
        raise PermissionError("Read-only olmayan veya kilitleyen SQL yapısı engellendi")
    return statement


def validate_read_only_sql(sql: str, dialect: str | None = None) -> str:
    _parse_single_select(sql, dialect=dialect)
    return sql.strip().rstrip(";")


def validate_dataset_sql(sql: str) -> str:
    statement = _parse_single_select(sql, dialect="duckdb")
    if _EXTERNAL_DATA_FUNCTION.search(sql):
        raise PermissionError("Dataset SQL yalnızca kayıtlı `data` tablosunu kullanabilir")

    cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
    allowed_tables = {"data", *cte_names}
    for table in statement.find_all(exp.Table):
        if table.args.get("db") or table.args.get("catalog"):
            raise PermissionError("Dataset SQL içinde schema/catalog erişimi engellendi")
        table_name = table.name.lower()
        if not table_name or table_name not in allowed_tables:
            raise PermissionError(
                f"Dataset SQL yalnızca `data` tablosuna erişebilir; engellenen tablo: {table_name or '?'}"
            )
    return sql.strip().rstrip(";")


def redact_possible_pii(text: str) -> str:
    out = text
    for pattern in [*PII_PATTERNS, *SECRET_PATTERNS]:
        out = pattern.sub("[REDACTED]", out)
    return out


def validate_public_web_query(query: str) -> str:
    clean = query.strip()
    if not clean:
        raise ValueError("Web sorgusu boş olamaz")
    if len(clean) > 500:
        raise PermissionError("Web sorgusu gereğinden uzun; ham şirket/veri satırı göndermeyin")
    for pattern in [*PII_PATTERNS, *SECRET_PATTERNS]:
        if pattern.search(clean):
            raise PermissionError(
                "Web sorgusunda olası kişisel veri veya secret tespit edildi; yerel veriyi internete göndermeyin"
            )
    return clean


def _host_is_local_or_private(host: str) -> bool:
    normalized = host.strip("[]").lower()
    if normalized in {"localhost", "127.0.0.1", "::1"} or normalized.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return bool(address.is_private or address.is_loopback or address.is_link_local)


def is_local_or_private_url(url: str) -> bool:
    parsed = urlparse(url)
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and _host_is_local_or_private(parsed.hostname)
    )


def validate_ollama_endpoint(url: str, allow_remote: bool = False) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise PermissionError("Ollama adresi geçerli bir http/https URL olmalı")
    if not allow_remote and not _host_is_local_or_private(parsed.hostname):
        raise PermissionError(
            "Uzak Ollama endpoint'i varsayılan gizlilik politikasıyla engellendi. "
            "Yalnızca bilinçli hybrid kullanım için LAC_ALLOW_REMOTE_OLLAMA=true ayarlayın."
        )
    return url.rstrip("/")


def validate_local_model_name(model: str, allow_cloud: bool = False) -> str:
    normalized = model.strip()
    if not normalized:
        raise ValueError("Model adı boş olamaz")
    if not allow_cloud and (
        normalized.lower().endswith(":cloud") or "/cloud" in normalized.lower()
    ):
        raise PermissionError(
            "Cloud model etiketi local-only modda engellendi. Açmak için LAC_ALLOW_CLOUD_MODELS=true gerekir."
        )
    return normalized


def validate_external_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise PermissionError("Yalnızca http/https dış URL'ler desteklenir")
    if _host_is_local_or_private(parsed.hostname):
        raise PermissionError("Web aracı yerel ağ/localhost hedeflerine erişemez")
    return url
