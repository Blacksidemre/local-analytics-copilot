from __future__ import annotations

import re
from pathlib import Path

from fastapi import UploadFile

from lacopilot.audit import audit
from lacopilot.config import get_settings
from lacopilot.ingestion import SUPPORTED_TABLE_EXTENSIONS, IngestionError, source_manifest

_WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_upload_name(filename: str | None) -> str:
    raw = Path(filename or "dataset").name
    cleaned = _WINDOWS_FORBIDDEN.sub("_", raw).strip().rstrip(". ")
    if not cleaned:
        cleaned = "dataset"
    path = Path(cleaned)
    stem = path.stem[:140].strip().rstrip(". ") or "dataset"
    if stem.upper() in _RESERVED_WINDOWS_NAMES:
        stem = f"dataset_{stem}"
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_TABLE_EXTENSIONS:
        raise IngestionError(
            "unsupported_type",
            f"Desteklenmeyen dosya tipi: {suffix or '(uzantı yok)'}",
            details={"supported": sorted(SUPPORTED_TABLE_EXTENSIONS)},
        )
    return f"{stem}{suffix}"


def _available_destination(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    source = Path(filename)
    for version in range(2, 10000):
        candidate = directory / f"{source.stem}_{version}{source.suffix}"
        if not candidate.exists():
            return candidate
    raise IngestionError("name_exhausted", "Dosya için boş bir sürüm adı bulunamadı.")


def validate_file_signature(path: Path) -> None:
    suffix = path.suffix.lower()
    with path.open("rb") as source:
        head = source.read(16)
        if path.stat().st_size >= 4:
            source.seek(-4, 2)
            tail = source.read(4)
        else:
            tail = b""
    if not head:
        raise IngestionError("empty_file", "Yüklenen dosya boş.")
    if suffix in {".xlsx", ".xlsm"} and not head.startswith(b"PK"):
        raise IngestionError(
            "signature_mismatch",
            "Dosya uzantısı Excel olsa da içerik geçerli bir XLSX/XLSM paketi değil.",
            hint="Dosyayı Excel'de yeniden .xlsx olarak kaydedin.",
        )
    if suffix == ".xls" and not head.startswith(b"\xd0\xcf\x11\xe0"):
        raise IngestionError(
            "signature_mismatch",
            "Dosya uzantısı .xls olsa da içerik eski Excel biçimi değil.",
            hint="Dosyayı .xlsx olarak kaydedin.",
        )
    if suffix in {".parquet", ".pq"} and not (head.startswith(b"PAR1") and tail == b"PAR1"):
        raise IngestionError(
            "signature_mismatch",
            "Dosya geçerli bir Parquet imzası taşımıyor.",
        )
    if suffix in {".csv", ".json", ".jsonl"} and b"\x00" in head:
        raise IngestionError(
            "signature_mismatch",
            "Metin tablosu olarak yüklenen dosya binary içerik taşıyor.",
        )


async def save_uploaded_dataset(upload: UploadFile) -> tuple[Path, dict]:
    settings = get_settings()
    filename = safe_upload_name(upload.filename)
    destination = _available_destination(settings.incoming_dir, filename)
    limit = int(settings.max_file_mb) * 1024 * 1024
    size = 0
    try:
        with destination.open("xb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise IngestionError(
                        "file_too_large",
                        f"Dosya {settings.max_file_mb} MB sınırını aşıyor.",
                        details={"max_bytes": limit},
                    )
                target.write(chunk)
        validate_file_signature(destination)
        manifest = source_manifest(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    relative = destination.resolve().relative_to(settings.workspace.resolve())
    audit(
        settings.logs_dir,
        "dataset_upload",
        file=str(relative),
        size_bytes=size,
        format=manifest["format"],
    )
    return destination, manifest
