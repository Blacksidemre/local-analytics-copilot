import { execFileSync, spawnSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";

type PrintedCommand = {
  executable: string;
  args: string[];
  cwd: string;
  shell: boolean;
};

const script = path.join(process.cwd(), "scripts", "run-next.mjs");

function printCommand(mode: "dev" | "start", host?: string): PrintedCommand {
  const env = { ...process.env };
  if (host === undefined) delete env.HERMETIC_HOST;
  else env.HERMETIC_HOST = host;
  return JSON.parse(
    execFileSync(process.execPath, [script, mode, "--print-command"], {
      cwd: process.cwd(),
      encoding: "utf8",
      env,
    })
  ) as PrintedCommand;
}

describe("cross-platform Next launcher", () => {
  it("starts dev without POSIX shell syntax and uses the default loopback host", () => {
    const command = printCommand("dev");

    expect(command.executable).toBe(process.execPath);
    expect(command.shell).toBe(false);
    expect(command.args[0]).toBe("--import");
    expect(new URL(command.args[1]).protocol).toBe("file:");
    expect(command.args[1]).not.toMatch(/^[a-z]:/i);
    expect(decodeURIComponent(new URL(command.args[1]).pathname)).toMatch(
      /scripts[/\\]server-timeouts\.mjs$/
    );
    expect(command.args[2]).toMatch(/next[/\\]dist[/\\]bin[/\\]next$/);
    expect(command.args.slice(-3)).toEqual(["dev", "-H", "127.0.0.1"]);
  });

  it("passes an explicit host to production start without interpolation", () => {
    const command = printCommand("start", "0.0.0.0");

    expect(command.args.slice(-3)).toEqual(["start", "-H", "0.0.0.0"]);
    expect(command.args.join(" ")).not.toContain("${HERMETIC_HOST");
    expect(command.args.join(" ")).not.toContain("NODE_OPTIONS=");
  });

  it("preloads the generated file URL in a real Node child process", () => {
    const command = printCommand("dev");
    const result = spawnSync(
      command.executable,
      ["--import", command.args[1], "--eval", "process.stdout.write('preload-ok')"],
      {
        cwd: command.cwd,
        encoding: "utf8",
        env: process.env,
      }
    );

    expect(result.status, result.stderr).toBe(0);
    expect(result.stdout).toBe("preload-ok");
    expect(result.stderr).toContain("[server-timeouts] preload active");
  });
});
