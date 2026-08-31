#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  checkDesktopPrerequisites,
  printDesktopPrerequisiteFailure,
} from "./desktop-prerequisites.mjs";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "..");
const require = createRequire(import.meta.url);

export function buildDesktopCommand(mode) {
  if (mode !== "dev") throw new Error("Usage: node scripts/run-desktop.mjs dev");
  return {
    executable: process.execPath,
    args: [require.resolve("@tauri-apps/cli/tauri.js"), mode],
    cwd: repositoryRoot,
    shell: false,
  };
}

let command;
try {
  command = buildDesktopCommand(process.argv[2]);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

if (command && process.argv.includes("--check-prerequisites")) {
  const prerequisites = checkDesktopPrerequisites();
  if (prerequisites.ok) {
    console.log(JSON.stringify(prerequisites));
  } else {
    printDesktopPrerequisiteFailure(prerequisites);
    process.exitCode = 1;
  }
} else if (command && process.argv.includes("--print-command")) {
  console.log(JSON.stringify(command));
} else if (command) {
  const prerequisites = checkDesktopPrerequisites();
  if (!prerequisites.ok) {
    printDesktopPrerequisiteFailure(prerequisites);
    process.exitCode = 1;
  } else {
    const child = spawn(command.executable, command.args, {
      cwd: command.cwd,
      env: process.env,
      shell: command.shell,
      stdio: "inherit",
    });
    child.once("error", (error) => {
      console.error(`[desktop] ${error.message}`);
      process.exitCode = 1;
    });
    child.once("exit", (code) => {
      process.exitCode = code ?? 1;
    });
  }
}
