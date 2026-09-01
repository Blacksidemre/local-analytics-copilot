import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const VC_COMPONENT = "Microsoft.VisualStudio.Component.VC.Tools.x86.x64";

export function evaluateDesktopPrerequisites({
  platform,
  cargoAvailable,
  rustcAvailable,
  linkerAvailable,
  visualCppInstalled,
}) {
  if (platform !== "win32") return { ok: true, errors: [] };

  const errors = [];
  if (!cargoAvailable || !rustcAvailable) {
    errors.push({
      code: "rust_toolchain_missing",
      message: "Rust MSVC toolchain bulunamadı.",
      hint: "rustup ile stable-x86_64-pc-windows-msvc toolchain kurun ve terminali yeniden açın.",
    });
  }
  if (!linkerAvailable && !visualCppInstalled) {
    errors.push({
      code: "visual_cpp_build_tools_missing",
      message: "Windows C++ linker (link.exe) ve Visual C++ Build Tools bulunamadı.",
      hint: 'Visual Studio Installer içinde "Desktop development with C++", MSVC x64/x86 tools ve Windows 10/11 SDK bileşenlerini kurun.',
    });
  }
  return { ok: errors.length === 0, errors };
}

function commandSucceeds(executable, args) {
  const result = spawnSync(executable, args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  return !result.error && result.status === 0;
}

function findVswhere(environment) {
  const candidates = [environment["ProgramFiles(x86)"], environment.ProgramFiles]
    .filter(Boolean)
    .map((root) => join(root, "Microsoft Visual Studio", "Installer", "vswhere.exe"));
  const installed = candidates.find((candidate) => existsSync(candidate));
  if (installed) return installed;

  const located = spawnSync("where.exe", ["vswhere.exe"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
    windowsHide: true,
  });
  return located.status === 0 ? (located.stdout.split(/\r?\n/).find(Boolean) ?? null) : null;
}

function hasVisualCppBuildTools(environment) {
  const vswhere = findVswhere(environment);
  if (!vswhere) return false;
  const result = spawnSync(
    vswhere,
    ["-latest", "-products", "*", "-requires", VC_COMPONENT, "-property", "installationPath"],
    {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    }
  );
  return !result.error && result.status === 0 && result.stdout.trim().length > 0;
}

export function checkDesktopPrerequisites({
  platform = process.platform,
  environment = process.env,
} = {}) {
  if (platform !== "win32") return { ok: true, errors: [] };
  return evaluateDesktopPrerequisites({
    platform,
    cargoAvailable: commandSucceeds("cargo", ["--version"]),
    rustcAvailable: commandSucceeds("rustc", ["--version"]),
    linkerAvailable: commandSucceeds("where.exe", ["link.exe"]),
    visualCppInstalled: hasVisualCppBuildTools(environment),
  });
}

export function printDesktopPrerequisiteFailure(report) {
  console.error("\n[desktop] Windows masaüstü önkoşulları eksik:");
  for (const error of report.errors) {
    console.error(`- ${error.message}`);
    console.error(`  ${error.hint}`);
  }
  console.error("\nKurulumdan sonra yeni bir terminal açıp aynı komutu yeniden çalıştırın.\n");
}
