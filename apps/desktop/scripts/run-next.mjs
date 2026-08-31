#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "..");
const require = createRequire(import.meta.url);

function buildCommand(mode) {
  if (mode !== "dev" && mode !== "start") {
    throw new Error("Usage: node scripts/run-next.mjs <dev|start> [--print-command]");
  }
  const host = process.env.HERMETIC_HOST?.trim() || "127.0.0.1";
  return {
    executable: process.execPath,
    args: [
      "--import",
      pathToFileURL(resolve(scriptDirectory, "server-timeouts.mjs")).href,
      require.resolve("next/dist/bin/next"),
      mode,
      "-H",
      host,
    ],
    cwd: repositoryRoot,
    shell: false,
  };
}

let command;
try {
  command = buildCommand(process.argv[2]);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

if (command && process.argv.includes("--print-command")) {
  console.log(JSON.stringify(command));
} else if (command) {
  const child = spawn(command.executable, command.args, {
    cwd: command.cwd,
    env: process.env,
    shell: command.shell,
    stdio: "inherit",
  });
  child.once("error", (error) => {
    console.error(`[run-next] ${error.message}`);
    process.exitCode = 1;
  });
  child.once("exit", (code) => {
    process.exitCode = code ?? 1;
  });
}
