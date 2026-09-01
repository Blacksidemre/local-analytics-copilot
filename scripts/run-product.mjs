#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import net from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "..");
const desktopRoot = resolve(repositoryRoot, "apps", "desktop");
const mode = process.argv[2] ?? "web";
const backendPort = boundedPort(process.env.LAC_BRIDGE_PORT, 8765);
const frontendPort = boundedPort(process.env.LAC_UI_PORT, 3000);
const backendUrl = `http://127.0.0.1:${backendPort}`;
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
const children = new Set();
let shuttingDown = false;

export function boundedPort(raw, fallback) {
  if (raw === undefined || raw === "") return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 1024 || value > 65535) {
    throw new Error(`Invalid local port: ${raw}`);
  }
  return value;
}

export function productCommands({ platform = process.platform } = {}) {
  const venvPython = resolve(
    repositoryRoot,
    ".venv",
    platform === "win32" ? "Scripts/python.exe" : "bin/python"
  );
  const python = process.env.LAC_PYTHON || (existsSync(venvPython) ? venvPython : "python");
  const pnpmEntrypoint = process.env.npm_execpath?.trim();
  const pnpm =
    pnpmEntrypoint && /pnpm(?:\.c?js)?$/i.test(pnpmEntrypoint)
      ? { executable: process.execPath, prefixArgs: [pnpmEntrypoint] }
      : {
          executable: platform === "win32" ? "pnpm.cmd" : "pnpm",
          prefixArgs: [],
        };
  return {
    backend: {
      executable: python,
      args: [
        "-m",
        "uvicorn",
        "lacopilot.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        String(backendPort),
      ],
      cwd: repositoryRoot,
    },
    web: { executable: pnpm.executable, args: [...pnpm.prefixArgs, "dev"], cwd: desktopRoot },
    desktop: {
      executable: pnpm.executable,
      args: [...pnpm.prefixArgs, "desktop:dev"],
      cwd: desktopRoot,
    },
  };
}

async function jsonHealth(url, predicate) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(1500), cache: "no-store" });
    if (!response.ok) return false;
    return predicate(await response.json());
  } catch {
    return false;
  }
}

function portOccupied(port) {
  return new Promise((resolvePromise) => {
    const socket = net.createConnection({ host: "127.0.0.1", port });
    socket.setTimeout(800);
    socket.once("connect", () => {
      socket.destroy();
      resolvePromise(true);
    });
    const unavailable = () => {
      socket.destroy();
      resolvePromise(false);
    };
    socket.once("error", unavailable);
    socket.once("timeout", unavailable);
  });
}

async function waitFor(label, probe, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await probe()) return;
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 300));
  }
  throw new Error(`${label} did not become ready within ${Math.ceil(timeoutMs / 1000)} seconds`);
}

function startChild(command, environment) {
  const child = spawn(command.executable, command.args, {
    cwd: command.cwd,
    env: environment,
    shell: false,
    stdio: "inherit",
    windowsHide: false,
    detached: process.platform !== "win32",
  });
  children.add(child);
  child.once("exit", () => children.delete(child));
  child.once("error", (error) => {
    console.error(`[launcher] ${error.message}`);
  });
  return child;
}

function stopChild(child) {
  if (!child.pid || child.exitCode !== null) return;
  if (process.platform === "win32") {
    spawnSync("taskkill.exe", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      windowsHide: true,
    });
    return;
  }
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {
    child.kill("SIGTERM");
  }
}

function shutdown(exitCode = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) stopChild(child);
  process.exitCode = exitCode;
}

async function main() {
  if (!new Set(["web", "desktop"]).has(mode)) {
    throw new Error("Usage: node scripts/run-product.mjs web|desktop");
  }
  const commands = productCommands();
  if (process.argv.includes("--print-config")) {
    console.log(JSON.stringify({ mode, backendUrl, frontendUrl, commands }, null, 2));
    return;
  }
  if (!existsSync(resolve(desktopRoot, "package.json"))) {
    throw new Error("Canonical desktop source is missing from apps/desktop");
  }

  const backendHealthy = () =>
    jsonHealth(`${backendUrl}/health`, (value) => value?.data_bridge?.status === "ready");
  if (!(await backendHealthy())) {
    if (await portOccupied(backendPort)) {
      throw new Error(`Port ${backendPort} is occupied by a service other than LAC Data Bridge`);
    }
    console.log("[launcher] Starting deterministic analytics backend...");
    startChild(commands.backend, {
      ...process.env,
      PYTHONPATH: [resolve(repositoryRoot, "src"), process.env.PYTHONPATH]
        .filter(Boolean)
        .join(process.platform === "win32" ? ";" : ":"),
      PYTHONUTF8: "1",
      PYTHONIOENCODING: "utf-8",
    });
    await waitFor("LAC Data Bridge", backendHealthy, 45_000);
  } else {
    console.log("[launcher] Existing LAC Data Bridge is ready.");
  }

  const environment = {
    ...process.env,
    NEXT_PUBLIC_LAC_HYBRID: "1",
    LAC_BRIDGE_URL: backendUrl,
    HERMETIC_HOST: "127.0.0.1",
    PORT: String(frontendPort),
  };
  const uiHealthy = () =>
    jsonHealth(`${frontendUrl}/api/lac/api/v1/health`, (value) => value?.data_bridge?.status === "ready");

  if (mode === "web") {
    if (!(await uiHealthy())) {
      if (await portOccupied(frontendPort)) {
        throw new Error(`Port ${frontendPort} is occupied by a service other than LAC desktop UI`);
      }
      console.log("[launcher] Starting Local Analytics Copilot UI...");
      const ui = startChild(commands.web, environment);
      ui.once("exit", (code) => shutdown(code ?? 1));
      await waitFor("Local Analytics Copilot UI", uiHealthy, 90_000);
    } else {
      console.log("[launcher] Existing Local Analytics Copilot UI is ready.");
    }
    console.log(`[launcher] Ready: ${frontendUrl}`);
    await new Promise(() => {});
    return;
  }

  console.log("[launcher] Starting Tauri desktop shell...");
  const desktop = startChild(commands.desktop, environment);
  const exitCode = await new Promise((resolvePromise) => {
    desktop.once("exit", (code) => resolvePromise(code ?? 1));
  });
  shutdown(exitCode);
}

for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.once(signal, () => shutdown(0));
}

main().catch((error) => {
  console.error(`[launcher] ${error instanceof Error ? error.message : String(error)}`);
  shutdown(1);
});
