from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


@dataclass
class HardwareProfile:
    os: str
    cpu: str
    ram_gb: float | None
    gpu: str | None
    vram_gb: float | None
    free_disk_gb: float | None
    recommended_fast_model: str
    recommended_main_model: str
    recommended_deep_model: str
    notes: list[str]


def _nvidia() -> tuple[str | None, float | None]:
    try:
        out = (
            subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            .strip()
            .splitlines()[0]
        )
        name, memory_mb = [x.strip() for x in out.rsplit(",", 1)]
        return name, round(float(memory_mb) / 1024, 1)
    except Exception:
        return None, None


def detect_hardware() -> dict:
    ram = round(psutil.virtual_memory().total / (1024**3), 1) if psutil else None
    gpu, vram = _nvidia()
    try:
        free_disk = round(shutil.disk_usage(os.getcwd()).free / (1024**3), 1)
    except Exception:
        free_disk = None

    if vram and vram >= 15:
        fast, main, deep = "qwen3.5:9b", "qwen3.5:9b", "gpt-oss:20b"
        notes = [
            "16 GB sınıfı VRAM: qwen3.5:9b günlük tool-calling ve analiz orkestrasyonu için güçlü/hızlı bir başlangıçtır.",
            "gpt-oss:20b yaklaşık 14 GB model dosyasıyla ağır reasoning görevleri için denenebilir; context büyüdükçe VRAM/RAM kullanımı artar.",
            "27B+ modeller RAM offload ile çalışabilir ancak gecikme belirgin artabilir.",
        ]
    elif vram and vram >= 10:
        fast, main, deep = "qwen3.5:9b", "qwen3.5:9b", "gemma4:12b"
        notes = ["12B model için context/VRAM ayarı gerekebilir."]
    elif vram and vram >= 6:
        fast, main, deep = "qwen3.5:4b", "qwen3.5:9b", "qwen3.5:9b"
        notes = ["Küçük model günlük işler için daha akıcı olacaktır."]
    else:
        fast, main, deep = "qwen3.5:4b", "qwen3.5:4b", "qwen3.5:9b"
        notes = ["GPU algılanmadı/düşük VRAM; CPU/RAM inference daha yavaş olabilir."]

    return asdict(
        HardwareProfile(
            os=f"{platform.system()} {platform.release()}",
            cpu=platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
            ram_gb=ram,
            gpu=gpu,
            vram_gb=vram,
            free_disk_gb=free_disk,
            recommended_fast_model=fast,
            recommended_main_model=main,
            recommended_deep_model=deep,
            notes=notes,
        )
    )
