from __future__ import annotations

from lacopilot.config import get_settings
from lacopilot.knowledge import KnowledgeBase


def knowledge_ingest(file_path: str, embed_model: str = "", ocr: bool = False) -> dict:
    """Ingest a workspace document into the local knowledge base. Optional Ollama embedding model can be supplied."""
    kb = KnowledgeBase(get_settings().knowledge_db)
    return kb.ingest(file_path, embed_model=embed_model or None, ocr=ocr)


def knowledge_search(query: str, top_k: int = 5, embed_model: str = "") -> dict:
    """Search the local company/orientation knowledge base. Returns grounded source chunks."""
    kb = KnowledgeBase(get_settings().knowledge_db)
    rows = kb.search(query, top_k=max(1, min(top_k, 12)), embed_model=embed_model or None)
    return {
        "query": query,
        "results": rows,
        "instruction": "Base company-specific answers on these chunks; if insufficient, state that the knowledge base does not support the answer.",
    }
