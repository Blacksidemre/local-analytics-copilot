import { execFileSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { evaluateDesktopPrerequisites } from "../../scripts/desktop-prerequisites.mjs";

type PrintedCommand = {
  executable: string;
  args: string[];
  cwd: string;
  shell: boolean;
};

const script = path.join(process.cwd(), "scripts", "run-desktop.mjs");

describe("cross-platform Tauri launcher", () => {
  it("uses the Node-resolved Tauri CLI without shell interpolation", () => {
    const command = JSON.parse(
      execFileSync(process.execPath, [script, "dev", "--print-command"], {
        cwd: process.cwd(),
        encoding: "utf8",
      })
    ) as PrintedCommand;

    expect(command.executable).toBe(process.execPath);
    expect(command.args[0]).toMatch(/@tauri-apps[/\\]cli[/\\]tauri\.js$/);
    expect(command.args[1]).toBe("dev");
    expect(command.shell).toBe(false);
  });

  it("does not gate Linux or macOS on Windows-only prerequisites", () => {
    for (const platform of ["linux", "darwin"]) {
      expect(
        evaluateDesktopPrerequisites({
          platform,
          cargoAvailable: false,
          rustcAvailable: false,
          linkerAvailable: false,
          visualCppInstalled: false,
        })
      ).toEqual({ ok: true, errors: [] });
    }
  });

  it("reports the actionable Windows Rust and Visual C++ blockers", () => {
    const result = evaluateDesktopPrerequisites({
      platform: "win32",
      cargoAvailable: false,
      rustcAvailable: false,
      linkerAvailable: false,
      visualCppInstalled: false,
    });

    expect(result.ok).toBe(false);
    expect(result.errors.map((error) => error.code)).toEqual([
      "rust_toolchain_missing",
      "visual_cpp_build_tools_missing",
    ]);
    expect(result.errors[1]?.hint).toContain("Desktop development with C++");
    expect(result.errors[1]?.hint).toContain("Windows 10/11 SDK");
  });

  it("accepts Visual C++ discovery even when link.exe is not on the caller PATH", () => {
    expect(
      evaluateDesktopPrerequisites({
        platform: "win32",
        cargoAvailable: true,
        rustcAvailable: true,
        linkerAvailable: false,
        visualCppInstalled: true,
      })
    ).toEqual({ ok: true, errors: [] });
  });

  it("keeps package scripts free of POSIX-only environment syntax", async () => {
    const packageJson = await import("../../package.json");
    const scripts = packageJson.default.scripts as Record<string, string>;

    expect(scripts["desktop:dev"]).toBe("node scripts/run-desktop.mjs dev");
    expect(scripts["desktop:dev"]).not.toMatch(/NODE_OPTIONS=|\$\{|&&/);
  });
});
