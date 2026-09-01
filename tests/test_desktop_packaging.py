from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lacopilot.desktop_entry import desktop_port

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_backend_port_is_bounded():
    assert desktop_port("8765") == 8765
    for value in ("0", "1023", "65536", "not-a-port"):
        with pytest.raises(ValueError):
            desktop_port(value)


def test_pyinstaller_command_is_scoped_to_canonical_desktop_resource():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from build_lac_backend import TARGET, build_command
    finally:
        sys.path.pop(0)

    temporary = ROOT / "build" / "test-desktop-package"
    command = build_command(temporary / "dist", temporary / "work", temporary / "spec")
    assert command[:3] == [sys.executable, "-m", "PyInstaller"]
    assert "--onedir" in command
    assert command[command.index("--collect-all") + 1] == "lacopilot"
    assert command[-1] == str(ROOT / "src" / "lacopilot" / "desktop_entry.py")
    assert TARGET == ROOT / "apps" / "desktop" / "src-tauri" / "lac-backend"
    assert "--onefile" not in command


def test_desktop_builder_invokes_tauri_through_node_not_a_cmd_shim():
    source = (ROOT / "apps" / "desktop" / "scripts" / "build-desktop.mjs").read_text(
        encoding="utf-8"
    )
    assert 'require.resolve("@tauri-apps/cli/tauri.js")' in source
    assert 'run("pnpm"' not in source
