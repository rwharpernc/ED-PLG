#!/usr/bin/env node
/**
 * Zip dist/EDPLG into dist/EDPLG-v<version>.zip for distribution.
 *
 * Usage:  node scripts/package.mjs   (run `npm run build` first)
 * Output: dist/EDPLG-v<version>.zip
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const sourceDir = path.join(root, "dist", "EDPLG");

if (!fs.existsSync(sourceDir)) {
  console.error(`${sourceDir} does not exist — run "npm run build" first.`);
  process.exit(1);
}

const version = fs
  .readFileSync(path.join(root, "plugin", "__init__.py"), "utf8")
  .match(/__version__\s*=\s*["']([^"']+)["']/)?.[1] ?? "0.0.0";

const zipPath = path.join(root, "dist", `EDPLG-v${version}.zip`);

if (fs.existsSync(zipPath)) {
  fs.rmSync(zipPath);
}

// Zip the EDPLG folder itself (not just its contents), so extracting the
// archive drops a ready-to-copy EDPLG/ folder straight into the EDMC
// plugins directory.
const result = spawnSync(
  "powershell.exe",
  [
    "-NoProfile",
    "-NonInteractive",
    "-Command",
    `Compress-Archive -Path '${sourceDir}' -DestinationPath '${zipPath}' -Force`,
  ],
  { stdio: "inherit" },
);

if (result.status !== 0) {
  console.error("Compress-Archive failed.");
  process.exit(result.status ?? 1);
}

console.log(`Packaged ED-PLG v${version} -> ${zipPath}`);
