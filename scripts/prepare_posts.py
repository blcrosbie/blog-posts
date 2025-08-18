#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict, Any, Optional

import yaml  # pip install pyyaml

CURVY_TO_STRAIGHT = {
    "“": '"', "”": '"', "„": '"',
    "‘": "'", "’": "'", "‚": "'",
    "—": "-", "–": "-",
}

MD_EXTS = {".md", ".mdx"}

def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"(^-|-$)", "", s)
    return s

def strip_date_prefix(basename_no_ext: str) -> Tuple[str, Optional[str]]:
    """
    If filename starts with YYYY-MM-DD-, return (rest, 'YYYY-MM-DD'), else (basename, None).
    """
    parts = basename_no_ext.split("-")
    if len(parts) >= 4 and re.fullmatch(r"\d{4}", parts[0]) and re.fullmatch(r"\d{2}", parts[1]) and re.fullmatch(r"\d{2}", parts[2]):
        yyyy, mm, dd = parts[0], parts[1], parts[2]
        try:
            # Validate date
            dt = datetime(int(yyyy), int(mm), int(dd))
            return "-".join(parts[3:]), dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return basename_no_ext, None

def normalize_quotes(text: str) -> str:
    return "".join(CURVY_TO_STRAIGHT.get(ch, ch) for ch in text)

def split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """
    Returns (frontmatter_dict, body). If none present, returns ({}, full_text).
    Accepts leading '---' then YAML then next '---'.
    """
    if not text.startswith("---"):
        return {}, text
    # Find the second '---' on a line by itself
    lines = text.splitlines(True)
    fm_end_idx = None
    for i in range(1, min(len(lines), 5000)):  # guard
        if lines[i].strip() == "---":
            fm_end_idx = i
            break
    if fm_end_idx is None:
        # Unclosed frontmatter; treat all as body
        return {}, text
    yaml_text = "".join(lines[1:fm_end_idx])
    body = "".join(lines[fm_end_idx+1:])
    try:
        data = yaml.safe_load(yaml_text) or {}
        if not isinstance(data, dict):
            data = {}
        return data, body
    except Exception:
        # If YAML is broken, return empty meta (we’ll rewrite) + keep original as body
        return {}, text

def ensure_frontmatter(meta: Dict[str, Any], basename_no_ext: str, inferred_date: Optional[str]) -> Dict[str, Any]:
    clean_name = slugify(strip_date_prefix(basename_no_ext)[0])
    # slug: always enforce from filename (your site uses frontmatter.slug only)
    meta["slug"] = clean_name

    # title: keep if present; else title-case from slug
    if not isinstance(meta.get("title"), str) or not meta["title"].strip():
        meta["title"] = clean_name.replace("-", " ").title()

    # date: if meta has valid date, keep; else if inferred_date from filename, use it
    date_str = meta.get("date")
    if isinstance(date_str, str):
        try:
            datetime.fromisoformat(date_str.strip())
        except Exception:
            if inferred_date:
                meta["date"] = inferred_date
    else:
        if inferred_date:
            meta["date"] = inferred_date

    # excerpt: make safe one-line (prevents YAML double-quote issues)
    if isinstance(meta.get("excerpt"), str):
        one_line = " ".join(meta["excerpt"].split())
        meta["excerpt"] = (one_line[:280] + "…") if len(one_line) > 280 else one_line

    # hero default
    if not isinstance(meta.get("hero"), str) or not meta["hero"].strip():
        meta["hero"] = "/images/bulb-icon.png"

    # tags: ensure array of strings if present
    if "tags" in meta and not isinstance(meta["tags"], list):
        meta["tags"] = [str(meta["tags"])]

    return meta

def dump_frontmatter(meta: Dict[str, Any]) -> str:
    # Keep key order readable
    preferred_keys = ["title", "slug", "date", "excerpt", "tags", "hero"]
    ordered: Dict[str, Any] = {}
    for k in preferred_keys:
        if k in meta:
            ordered[k] = meta[k]
    for k, v in meta.items():
        if k not in ordered:
            ordered[k] = v
    return "---\n" + yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True).strip() + "\n---\n"

def process_file(path: Path, write: bool) -> Tuple[str, Optional[str]]:
    """
    Returns (slug, error_message_or_None).
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = normalize_quotes(raw).replace("\r\n", "\n").replace("\r", "\n")

    meta, body = split_frontmatter(raw)
    basename_no_ext = path.stem
    clean_base, inferred_date = strip_date_prefix(basename_no_ext)

    meta = ensure_frontmatter(meta, basename_no_ext, inferred_date)
    slug = meta["slug"]

    new_text = dump_frontmatter(meta) + body.lstrip("\n")  # trim a leading blank
    if write and new_text != raw:
        path.write_text(new_text, encoding="utf-8")
    return slug, None

def main():
    ap = argparse.ArgumentParser(description="Prepare MD/MDX posts: fix frontmatter, ensure slug, prevent YAML issues.")
    ap.add_argument("--root", default="blog", help="Directory with posts (default: blog)")
    ap.add_argument("--check", action="store_true", help="Only check; do not write changes")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f":: error :: posts root not found: {root}", file=sys.stderr)
        sys.exit(1)

    slugs = {}
    errors = []
    changed = False

    for p in sorted(root.rglob("*")):
        if p.suffix.lower() not in MD_EXTS:
            continue
        try:
            before = p.read_text(encoding="utf-8", errors="replace")
            slug, err = process_file(p, write=not args.check)
            after = p.read_text(encoding="utf-8", errors="replace")
            if before != after:
                changed = True
            if err:
                errors.append(f"{p}: {err}")
            slugs.setdefault(slug, []).append(p)
        except Exception as e:
            errors.append(f"{p}: {e}")

    # duplicate slug check
    dupes = {s: ps for s, ps in slugs.items() if len(ps) > 1}
    for s, ps in dupes.items():
        errors.append(f"duplicate slug '{s}' in files: {', '.join(str(x) for x in ps)}")

    if errors:
        for e in errors:
            print(f":: error :: {e}", file=sys.stderr)
        sys.exit(1)

    if args.check and changed:
        print("Changes would be made (run without --check to write).")
        sys.exit(2)

    print("OK: posts validated." + (" (updated files)" if changed else ""))
    sys.exit(0)

if __name__ == "__main__":
    main()
