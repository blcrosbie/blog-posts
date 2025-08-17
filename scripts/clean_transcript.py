#!/usr/bin/env python3
# Usage:
#   python scripts/clean_transcript.py corpus/youtube/raw/2020-qgis-gee-plugin-part-1.txt \
#     -o corpus/youtube/clean/2020-qgis-gee-plugin-part-1.md
import argparse
import os
import re
from pathlib import Path

def clean_text(text: str) -> str:
    lines = text.splitlines()
    out = []
    for ln in lines:
        # Remove lines that are only timestamps
        if re.fullmatch(r"\s*\d{1,2}:\d{2}(?::\d{2})?\s*", ln):
            continue
        # Strip leading timestamps
        ln = re.sub(r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s+", "", ln)
        # Remove stage directions
        ln = re.sub(r"\[(music|applause|laughter|background)\]", "", ln, flags=re.I)
        out.append(ln)
    cleaned = "\n".join(out)
    # Collapse 3+ blank lines → 2
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Path to raw transcript .txt")
    ap.add_argument("-o", "--output", help="Output .md path (optional)")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")

    out_path = Path(args.output) if args.output else Path(
        str(in_path).replace("/raw/", "/clean/").replace("\\raw\\", "\\clean\\")
    ).with_suffix(".md")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    text = in_path.read_text(encoding="utf-8", errors="ignore")
    cleaned = clean_text(text)

    title = in_path.stem.replace("_", " ").replace("-", " ").title()
    md = f"# (Draft) {title}\n\n{cleaned}\n"
    out_path.write_text(md, encoding="utf-8")
    print("Wrote:", out_path)

if __name__ == "__main__":
    main()
