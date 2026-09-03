#!/usr/bin/env node
/**
 * Regenerate plugin/names_fdevids.py from EDCD/FDevIDs' microresources.csv.
 *
 * This is a maintenance step, not part of the ordinary build - it is the
 * only thing in this repo's tooling that touches the network. Run it
 * occasionally to pick up new Odyssey microresources, then commit the
 * regenerated file like any other source change.
 *
 * Usage:  node scripts/update-names.mjs
 * Output: plugin/names_fdevids.py
 */

import fs from "node:fs";
import https from "node:https";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const outputPath = path.join(root, "plugin", "names_fdevids.py");

const SOURCE_URL = "https://raw.githubusercontent.com/EDCD/FDevIDs/master/microresources.csv";

// ED-PLG only tracks these three (see CLAUDE.md's Scope) - FDevIDs also
// lists Consumable microresources (grenades, medkits, ...), which are out
// of scope and deliberately excluded here.
const TRACKED_CATEGORIES = new Set(["Component", "Item", "Data"]);

function fetchText(url) {
  return new Promise((resolve, reject) => {
    https
      .get(url, { headers: { "User-Agent": "ED-PLG update-names script" } }, (res) => {
        if (res.statusCode !== 200) {
          reject(new Error(`GET ${url} -> HTTP ${res.statusCode}`));
          res.resume();
          return;
        }
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
      })
      .on("error", reject);
  });
}

/** Minimal RFC 4180 CSV parser - handles quoted fields with embedded commas/quotes. */
function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const c = text[i];

    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += c;
      }
      continue;
    }

    if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      field = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
    } else {
      field += c;
    }
  }
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }

  return rows;
}

// Matches plugin/names.py's canonicalise(): lowercase, no spaces.
function canonicalise(name) {
  return name.toLowerCase().replaceAll(" ", "");
}

function pyStringLiteral(value) {
  return `"${value.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

async function main() {
  console.log(`Fetching ${SOURCE_URL} ...`);
  const csvText = await fetchText(SOURCE_URL);
  const rows = parseCsv(csvText);

  const [header, ...dataRows] = rows;
  const symbolCol = header.indexOf("symbol");
  const categoryCol = header.indexOf("category");
  const nameCol = header.indexOf("English name");

  if (symbolCol < 0 || categoryCol < 0 || nameCol < 0) {
    throw new Error(`Unexpected microresources.csv header: ${header.join(",")}`);
  }

  const names = new Map();
  for (const row of dataRows) {
    const category = row[categoryCol];
    if (!TRACKED_CATEGORIES.has(category)) continue;

    const key = canonicalise(row[symbolCol]);
    const displayName = row[nameCol];
    if (!key || !displayName) continue;

    names.set(key, displayName);
  }

  const entries = [...names.entries()].sort(([a], [b]) => a.localeCompare(b));

  const lines = [
    '"""Microresource display names imported from FDevIDs.',
    "",
    "AUTO-GENERATED - do not hand-edit. Regenerate with `npm run update-names`,",
    `which pulls Component/Item/Data rows from:`,
    `  ${SOURCE_URL}`,
    '"""',
    "",
    "from __future__ import annotations",
    "",
    "from typing import Dict",
    "",
    "# Keys are canonicalised (lowercase, no spaces) Frontier internal names.",
    "FDEVIDS_DISPLAY_NAMES: Dict[str, str] = {",
    ...entries.map(([key, value]) => `    ${pyStringLiteral(key)}: ${pyStringLiteral(value)},`),
    "}",
    "",
  ];

  fs.writeFileSync(outputPath, lines.join("\n"), "utf8");
  console.log(`Wrote ${entries.length} names -> ${path.relative(root, outputPath)}`);
}

main().catch((err) => {
  console.error(err.message ?? err);
  process.exit(1);
});
