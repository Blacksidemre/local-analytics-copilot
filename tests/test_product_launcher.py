from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "run-product.mjs"


def test_canonical_product_contains_desktop_source_and_attribution():
    assert (ROOT / "apps" / "desktop" / "package.json").is_file()
    assert (ROOT / "apps" / "desktop" / "LICENSE").is_file()
    assert (ROOT / "apps" / "desktop" / "THIRD-PARTY-NOTICES.md").is_file()
    assert (ROOT / "apps" / "desktop" / "src" / "spec" / "NOTICE.md").is_file()


def test_root_product_launcher_uses_shell_free_relative_commands():
    source = LAUNCHER.read_text(encoding="utf-8")
    assert 'resolve(repositoryRoot, "apps", "desktop")' in source
    assert "shell: false" in source
    assert '"lacopilot.app:app"' in source
    assert 'NEXT_PUBLIC_LAC_HYBRID: "1"' in source
    assert "LAC_BRIDGE_URL: backendUrl" in source
    assert "C:\\" not in source
    assert "/Users/" not in source


def test_root_product_launcher_prints_bounded_configuration():
    result = subprocess.run(
        ["node", str(LAUNCHER), "web", "--print-config"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    payload = json.loads(result.stdout)
    assert payload["backendUrl"] == "http://127.0.0.1:8765"
    assert payload["frontendUrl"] == "http://127.0.0.1:3000"
    assert payload["commands"]["backend"]["cwd"] == str(ROOT)
    assert payload["commands"]["web"]["cwd"] == str(ROOT / "apps" / "desktop")


def test_root_launcher_reuses_pnpm_js_entrypoint_without_cmd_shell(tmp_path):
    pnpm_entrypoint = tmp_path / "pnpm.cjs"
    pnpm_entrypoint.write_text("// launcher fixture\n", encoding="utf-8")
    environment = os.environ | {"npm_execpath": str(pnpm_entrypoint)}
    result = subprocess.run(
        ["node", str(LAUNCHER), "desktop", "--print-config"],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )

    command = json.loads(result.stdout)["commands"]["desktop"]
    assert Path(command["executable"]).resolve() == Path(shutil.which("node") or "node").resolve()
    assert command["args"][:2] == [str(pnpm_entrypoint), "desktop:dev"]
