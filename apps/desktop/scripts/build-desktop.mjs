#!/usr/bin/env node
/**
 * Build the Hermetic desktop executable (build log D15 / Phase 0c) for THIS platform.
 * Produces a platform installer/app under src-tauri/target/release/bundle/.
 *
 * Steps:
 *   1. cargo build --release the egress-fetch bin (the §6a remote-read edge) so the
 *      sidecar picks up the RELEASE binary, not debug.
 *   2. `tauri build` — its beforeBuildCommand (pnpm desktop:sidecar) assembles the
 *      Next standalone server + node + assets into src-tauri/sidecar, then Tauri
 *      bundles it as a resource and compiles the shell.
 *
 * Cross-platform release: run this ON each target OS (macOS/Windows/Linux). A single
 * host cannot produce all installers (native webview + code signing are per-OS). The
 * sidecar's `node` is THIS platform's node (build-desktop-sidecar copies process
 * execPath) — a cross-compile must drop in the target-triple node. See README.
 */
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import {
  checkDesktopPrerequisites,
  printDesktopPrerequisiteFailure,
} from "./desktop-prerequisites.mjs";

const ROOT = resolve(import.meta.dirname, "..");
const PRODUCT_ROOT = resolve(ROOT, "..", "..");
const require = createRequire(import.meta.url);
const prerequisites = checkDesktopPrerequisites();
if (!prerequisites.ok) {
  printDesktopPrerequisiteFailure(prerequisites);
  process.exit(1);
}
const run = (cmd, args, opts = {}) => {
  console.log(`\n$ ${cmd} ${args.join(" ")}`);
  execFileSync(cmd, args, { cwd: ROOT, stdio: "inherit", ...opts });
};

const packagedPython =
  process.env.LAC_PYTHON?.trim() ||
  (existsSync(
    resolve(
      PRODUCT_ROOT,
      ".venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python"
    )
  )
    ? resolve(
        PRODUCT_ROOT,
        ".venv",
        process.platform === "win32" ? "Scripts/python.exe" : "bin/python"
      )
    : process.platform === "win32"
      ? "python.exe"
      : "python3");

console.log("[desktop] 1/3 packaging deterministic LAC backend…");
run(packagedPython, [resolve(PRODUCT_ROOT, "scripts", "build_lac_backend.py")], {
  cwd: PRODUCT_ROOT,
});

console.log("[desktop] 2/3 building egress-fetch (release)…");
run("cargo", ["build", "--release", "--locked", "--bin", "egress-fetch"], {
  cwd: resolve(ROOT, "rust", "egress-core"),
});

console.log("[desktop] 3/3 tauri build (assembles both sidecars, bundles the app)…");
run(process.execPath, [require.resolve("@tauri-apps/cli/tauri.js"), "build"]);

console.log("\n[desktop] done — see src-tauri/target/release/bundle/");
