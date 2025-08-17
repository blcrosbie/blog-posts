#!/usr/bin/env node
// node scripts/clean-transcript.mjs corpus/youtube/raw/file.txt -o corpus/youtube/clean/file.md
import fs from "node:fs";
import path from "node:path";

const inPath = process.argv[2];
const outFlag = process.argv.indexOf("-o");
const outPath = outFlag > -1 ? process.argv[outFlag + 1] : inPath.replace("/raw/", "/clean/").replace(/\.txt$/i, ".md");

if (!inPath) {
  console.error("Usage: node scripts/clean-transcript.mjs <input.txt> [-o output.md]");
  process.exit(1);
}

let text = fs.readFileSync(inPath, "utf8");

// Remove obvious timestamp lines: "0:00" or "12:34 word" at start
text = text
  .split(/\r?\n/)
  .map(line => line
    .replace(/^\s*\d{1,2}:\d{2}(?::\d{2})?\s*$/g, "")           // lines that are JUST timestamps
    .replace(/^\s*\d{1,2}:\d{2}(?::\d{2})?\s+/g, "")            // leading timestamp + space
    .replace(/\[(Music|Applause|Laughter|Background)\]/gi, "")  // stage directions
  )
  .filter(Boolean)
  .join("\n");

// Collapse multiple blank lines
text = text.replace(/\n{3,}/g, "\n\n");

// Add a tiny preface header we can delete/edit later
const md = `# (Draft) ${path.basename(inPath, path.extname(inPath)).replace(/[-_]/g, " ")}

${text}
`;

fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, md, "utf8");
console.log("Wrote:", outPath);
