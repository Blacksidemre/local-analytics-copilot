from pathlib import Path

from lacopilot.config import get_settings
from lacopilot.knowledge import KnowledgeBase
from lacopilot.memory import LocalMemory


def setup(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LAC_WORKSPACE", str(tmp_path))
    get_settings.cache_clear()
    s = get_settings()
    s.ensure_dirs()
    return s


def test_memory_gate(tmp_path, monkeypatch):
    s = setup(tmp_path, monkeypatch)
    m = LocalMemory(s.memory_db)
    m.upsert("business_rule", "recovery", "Tahsilat / bakiye", status="candidate")
    cand = m.list(status="candidate")
    assert len(cand) == 1
    m.approve(cand[0]["id"])
    assert "recovery" in m.approved_context()


def test_local_knowledge(tmp_path, monkeypatch):
    s = setup(tmp_path, monkeypatch)
    f = s.knowledge_dir / "guide.txt"
    f.write_text("DPD gecikme gün sayısını ifade eden örnek bir eğitim notudur.", encoding="utf-8")
    kb = KnowledgeBase()
    ing = kb.ingest("knowledge/guide.txt")
    assert ing["chunks"] >= 1
    rows = kb.search("DPD", top_k=3)
    assert rows and "guide.txt" in rows[0]["path"]
