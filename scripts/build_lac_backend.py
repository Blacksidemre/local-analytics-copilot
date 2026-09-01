from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "apps" / "desktop" / "src-tauri" / "lac-backend"


def build_command(dist: Path, work: Path, spec: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "lac-backend",
        "--paths",
        str(ROOT / "src"),
        "--distpath",
        str(dist),
        "--workpath",
        str(work),
        "--specpath",
        str(spec),
        "--collect-all",
        "lacopilot",
        "--collect-all",
        "scipy",
        "--collect-all",
        "statsmodels",
        "--collect-all",
        "sklearn",
        str(ROOT / "src" / "lacopilot" / "desktop_entry.py"),
    ]


def main() -> None:
    if importlib.util.find_spec("PyInstaller") is None:
        raise SystemExit(
            "PyInstaller bulunamadı. Paketleme ortamında `python -m pip install -e .[desktop]` "
            "çalıştırın."
        )
    with tempfile.TemporaryDirectory(prefix="lac-backend-build-") as temporary:
        temporary_path = Path(temporary)
        dist = temporary_path / "dist"
        spec = temporary_path / "spec"
        spec.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            build_command(dist, temporary_path / "work", spec),
            cwd=ROOT,
            check=True,
        )
        built = dist / "lac-backend"
        executable = built / ("lac-backend.exe" if sys.platform == "win32" else "lac-backend")
        if not executable.is_file():
            raise SystemExit(f"Paketlenmiş backend executable bulunamadı: {executable}")
        if TARGET.exists():
            shutil.rmtree(TARGET)
        shutil.copytree(built, TARGET)
    print(f"[desktop] packaged LAC backend: {TARGET}")


if __name__ == "__main__":
    main()
