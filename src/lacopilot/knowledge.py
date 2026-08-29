from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

import numpy as np

from lacopilot.config import get_settings
from lacopilot.security import (
    resolve_workspace_path,
    validate_file_size,
    validate_local_model_name,
    validate_ollama_endpoint,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _embed_texts(texts: list[str], model: str) -> list[list[float]]:
    settings = get_settings()
    host = validate_ollama_endpoint(
        settings.ollama_host,
        allow_remote=settings.allow_remote_ollama,
    )
    model = validate_local_model_name(model, allow_cloud=settings.allow_cloud_models)
    from ollama import Client

    client = Client(host=host, timeout=settings.ollama_timeout_seconds)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), 32):
        response = client.embed(model=model, input=texts[start : start + 32])
        vectors.extend([list(map(float, vector)) for vector in response.embeddings])
    if len(vectors) != len(texts):
        raise RuntimeError("Embedding servisi beklenen sayıda vektör döndürmedi")
    return vectors


def _extract_text(path: Path, ocr: bool = False) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".sql", ".py", ".json", ".yaml", ".yml"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        from pypdf import PdfReader

        parts = []
        pages = PdfReader(str(path)).pages
        for i, page in enumerate(pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                parts.append(f"[Page {i}]\n{text}")
        if parts or not ocr:
            return "\n\n".join(parts)
        # Optional local OCR fallback for image-only PDFs. Requires Tesseract binary + Python extras.
        try:
            import fitz  # PyMuPDF
            import pytesseract
            from PIL import Image

            ocr_parts = []
            doc = fitz.open(str(path))
            for i, page in enumerate(doc, 1):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(img, lang="tur+eng")
                if text.strip():
                    ocr_parts.append(f"[Page {i} OCR]\n{text}")
            return "\n\n".join(ocr_parts)
        except Exception as exc:
            raise RuntimeError(
                "PDF metni çıkarılamadı. Görüntü tabanlı PDF için optional OCR gerekir: "
                "Tesseract + `pip install -e '.[ocr]'`. Ayrıntı: " + str(exc)
            ) from exc
    if suffix == ".docx":
        from docx import Document

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if suffix in {".csv", ".xlsx", ".xlsm"}:
        import pandas as pd

        if suffix == ".csv":
            df = pd.read_csv(path, nrows=5000)
            return df.to_csv(index=False)
        sheets = pd.read_excel(path, sheet_name=None, nrows=1000)
        return "\n\n".join(
            f"[Sheet {name}]\n{df.to_csv(index=False)}" for name, df in sheets.items()
        )
    raise ValueError(f"Bilgi tabanında desteklenmeyen dosya tipi: {suffix}")


def _chunks(text: str, size: int = 1200, overlap: int = 180) -> Iterable[str]:
    clean = re.sub(r"\r\n?", "\n", text).strip()
    if not clean:
        return
    pos = 0
    while pos < len(clean):
        end = min(len(clean), pos + size)
        if end < len(clean):
            cut = max(clean.rfind("\n", pos, end), clean.rfind(". ", pos, end))
            if cut > pos + size // 2:
                end = cut + 1
        chunk = clean[pos:end].strip()
        if chunk:
            yield chunk
        if end >= len(clean):
            break
        pos = max(pos + 1, end - overlap)


class KnowledgeBase:
    """Local RAG store with SQLite FTS5 and optional Ollama embeddings.

    FTS works without any embedding model. If `embed_model` is passed while Ollama is
    running, vectors are stored and hybrid search becomes available.
    """

    def __init__(self, db_path: Path | None = None):
        s = get_settings()
        self.db_path = db_path or s.knowledge_db
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init(self):
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS documents(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                sha256 TEXT NOT NULL,
                title TEXT,
                chunk_count INTEGER NOT NULL,
                ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS chunks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                vector_json TEXT,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            )""")
            try:
                con.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, content='chunks', content_rowid='id')"
                )
                con.executescript("""
                CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                  INSERT INTO chunks_fts(rowid,text) VALUES (new.id,new.text);
                END;
                CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                  INSERT INTO chunks_fts(chunks_fts,rowid,text) VALUES('delete',old.id,old.text);
                END;
                CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                  INSERT INTO chunks_fts(chunks_fts,rowid,text) VALUES('delete',old.id,old.text);
                  INSERT INTO chunks_fts(rowid,text) VALUES(new.id,new.text);
                END;
                """)
            except sqlite3.OperationalError:
                pass

    def ingest(
        self, workspace_relative_path: str, embed_model: str | None = None, ocr: bool = False
    ) -> dict:
        s = get_settings()
        path = resolve_workspace_path(s.workspace, workspace_relative_path)
        validate_file_size(path, s.max_file_mb)
        text = _extract_text(path, ocr=ocr)
        chunks = list(_chunks(text))
        if not chunks:
            raise ValueError(
                "Dosyadan indekslenebilir metin çıkarılamadı. Görüntü tabanlı PDF ise OCR seçeneğini kullanın."
            )
        digest = _sha256_file(path)
        vectors: list[list[float] | None] = [None] * len(chunks)
        embedding_warning: str | None = None
        if embed_model and chunks:
            try:
                vectors = _embed_texts(chunks, embed_model)
            except Exception as exc:
                vectors = [None] * len(chunks)
                embedding_warning = (
                    "Embedding başarısız; belge yalnızca yerel tam metin aramasıyla indekslendi: "
                    f"{type(exc).__name__}: {exc}"
                )

        rel = str(path.resolve().relative_to(s.workspace.resolve()))
        with self._connect() as con:
            old = con.execute("SELECT id,sha256 FROM documents WHERE path=?", (rel,)).fetchone()
            if old and old["sha256"] == digest:
                return {
                    "status": "unchanged",
                    "path": rel,
                    "chunks": int(old["id"] and len(chunks)),
                }
            if old:
                con.execute("DELETE FROM chunks WHERE document_id=?", (old["id"],))
                con.execute("DELETE FROM documents WHERE id=?", (old["id"],))
            cur = con.execute(
                "INSERT INTO documents(path,sha256,title,chunk_count) VALUES(?,?,?,?)",
                (rel, digest, path.stem, len(chunks)),
            )
            doc_id = cur.lastrowid
            con.executemany(
                "INSERT INTO chunks(document_id,chunk_index,text,vector_json) VALUES(?,?,?,?)",
                [
                    (doc_id, i, chunk, json.dumps(v) if v is not None else None)
                    for i, (chunk, v) in enumerate(zip(chunks, vectors, strict=True))
                ],
            )
        result = {
            "status": "ingested",
            "path": rel,
            "chunks": len(chunks),
            "embedded": any(v is not None for v in vectors),
        }
        if embedding_warning:
            result["warning"] = embedding_warning
        return result

    def ingest_folder(
        self, folder: str = "knowledge", embed_model: str | None = None, ocr: bool = False
    ) -> dict:
        s = get_settings()
        root = resolve_workspace_path(s.workspace, folder)
        supported = {
            ".pdf",
            ".docx",
            ".txt",
            ".md",
            ".csv",
            ".xlsx",
            ".xlsm",
            ".sql",
            ".json",
            ".yaml",
            ".yml",
        }
        results = []
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in supported:
                try:
                    results.append(
                        self.ingest(
                            str(p.resolve().relative_to(s.workspace.resolve())),
                            embed_model=embed_model,
                            ocr=ocr,
                        )
                    )
                except Exception as exc:
                    results.append(
                        {
                            "path": str(p.resolve().relative_to(s.workspace.resolve())),
                            "error": str(exc),
                        }
                    )
        return {"count": len(results), "results": results}

    def list_documents(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute("SELECT * FROM documents ORDER BY ingested_at DESC").fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, top_k: int = 5, embed_model: str | None = None) -> list[dict]:
        top_k = max(1, min(int(top_k), 20))
        lexical: list[dict] = []
        with self._connect() as con:
            try:
                rows = con.execute(
                    """SELECT c.id,c.chunk_index,c.text,c.vector_json,d.path,d.title,bm25(chunks_fts) AS score
                    FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid
                    JOIN documents d ON d.id=c.document_id
                    WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?""",
                    (query, top_k * 3),
                ).fetchall()
                lexical = [dict(r) for r in rows]
            except sqlite3.OperationalError:
                rows = con.execute(
                    """SELECT c.id,c.chunk_index,c.text,c.vector_json,d.path,d.title
                    FROM chunks c JOIN documents d ON d.id=c.document_id WHERE lower(c.text) LIKE ? LIMIT ?""",
                    (f"%{query.lower()}%", top_k * 3),
                ).fetchall()
                lexical = [dict(r) | {"score": 0.0} for r in rows]

        if not embed_model:
            return [{k: v for k, v in r.items() if k != "vector_json"} for r in lexical[:top_k]]

        try:
            qv = np.asarray(_embed_texts([query], embed_model)[0], dtype=float)
            with self._connect() as con:
                rows = con.execute("""SELECT c.id,c.chunk_index,c.text,c.vector_json,d.path,d.title
                    FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.vector_json IS NOT NULL""").fetchall()
            scored = []
            for r in rows:
                v = np.asarray(json.loads(r["vector_json"]), dtype=float)
                denom = np.linalg.norm(qv) * np.linalg.norm(v)
                score = float(np.dot(qv, v) / denom) if denom else 0.0
                scored.append(
                    {
                        "id": r["id"],
                        "chunk_index": r["chunk_index"],
                        "text": r["text"],
                        "path": r["path"],
                        "title": r["title"],
                        "semantic_score": score,
                    }
                )
            semantic = sorted(scored, key=lambda x: x["semantic_score"], reverse=True)[: top_k * 2]
            merged: dict[int, dict] = {
                r["id"]: {k: v for k, v in r.items() if k != "vector_json"} for r in lexical
            }
            for r in semantic:
                merged.setdefault(r["id"], r).update({"semantic_score": r["semantic_score"]})
            return sorted(
                merged.values(),
                key=lambda x: (x.get("semantic_score", 0.0), -x.get("score", 0.0)),
                reverse=True,
            )[:top_k]
        except Exception:
            return [{k: v for k, v in r.items() if k != "vector_json"} for r in lexical[:top_k]]
