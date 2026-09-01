import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

describe("offline desktop fonts", () => {
  it("bundles Geist locally without a build-time Google Fonts request", () => {
    const layout = readFileSync(path.join(process.cwd(), "src", "app", "layout.tsx"), "utf8");

    expect(layout).toContain('import "@fontsource-variable/geist"');
    expect(layout).toContain('import "@fontsource-variable/geist-mono"');
    expect(layout).not.toContain("next/font/google");
  });
});
