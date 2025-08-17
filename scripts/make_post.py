#!/usr/bin/env python3
# Usage (Windows PowerShell example):
#   $env:LLM_API_KEY="sk-..."            # or setx to persist; never commit keys
#   $env:LLM_MODEL="gpt-oss-20b"         # or "gpt-4o-mini"
#   $env:LLM_BASE_URL="https://api.openai.com/v1"   # default; swap for your OSS endpoint
#   python scripts/make_post.py "QGIS + Google Earth Engine: 92 Feeds, One Plugin" 2020-07-01 corpus/youtube/clean/2020-qgis-gee-plugin-part-1.md --out-blog blog --out-social social

import argparse
import os
import re
import json
from pathlib import Path
import requests
from datetime import datetime

BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
API_KEY  = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL    = os.getenv("LLM_MODEL", "gpt-oss-20b")
MAX_TOK  = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1200"))
TEMP     = float(os.getenv("LLM_TEMPERATURE", "0.7"))

def chat(system: str, user: str) -> str:
    if not API_KEY:
        raise RuntimeError("Missing LLM_API_KEY / OPENAI_API_KEY environment variable.")
    url = f"{BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "temperature": TEMP,
        "max_tokens": MAX_TOK,
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM error {resp.status_code}: {resp.text}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"(^-|-$)", "", s)
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("title")
    ap.add_argument("date", help="YYYY-MM-DD")
    ap.add_argument("source_md_path", help="Cleaned markdown transcript")
    ap.add_argument("--voice", default="prompts/VOICE_GUIDE.md")
    ap.add_argument("--out-blog", default="blog", help="Output dir for MDX")
    ap.add_argument("--out-social", default="social", help="Output dir for social posts")
    args = ap.parse_args()

    # Validate date
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        raise SystemExit("Date must be YYYY-MM-DD")

    notes = Path(args.source_md_path).read_text(encoding="utf-8")
    voice = Path(args.voice).read_text(encoding="utf-8") if Path(args.voice).exists() else (
        "Tone: candid, reflective, technical-but-human.\n"
        "Moves: analogy → contrast → lesson → pragmatic CTA.\n"
        "Cadence: short hooks; skim list; clean close.\n"
        "Stance: optimistic on tech; realistic on trade-offs.\n"
        "Lexicon: application vs education; adapt; B2B; CI/CD; GCP; geospatial."
    )

    # 1) MDX draft
    mdx_system = "You are Brandon Crosbie’s writing partner. Output only valid MDX."
    mdx_user = f"""VOICE_GUIDE:
{voice}

Create a 1200–1600 word MDX blog post with frontmatter:
---
title: "{args.title}"
date: "{args.date}"
excerpt: (one sentence)
tags: [geospatial, google-earth-engine, qgis]
hero: "/images/blog/gee-qgis.png"
---

Ground your claims ONLY in the SOURCE below. Use H2/H3 headings, include short callouts and code blocks where useful. No JSX components, just MDX.

SOURCE:
{notes}
"""
    mdx = chat(mdx_system, mdx_user)

    # 2) Social bullets (short)
    bullets_system = "Summarize for social drafting."
    bullets_user = f"Give 4–6 bullets (max ~600 chars total) of the key takeaways from this MDX:\n{mdx[:6000]}"
    bullets = chat(bullets_system, bullets_user)

    # 3) LinkedIn
    li_system = "You are Brandon writing for LinkedIn."
    li_user = f"""VOICE_GUIDE:
{voice}

Write a 900–1100 character LinkedIn post teeing up the blog "{args.title}".
Use the bullets verbatim where possible.
Structure: 1 strong hook line, 2–3 short paragraphs, 1 skim list, clear CTA to read the blog.
No more than 3 hashtags at the end.

BULLETS:
{bullets}
"""
    linkedin = chat(li_system, li_user)

    # 4) X
    x_system = "You are Brandon posting to X."
    x_user = f"""VOICE_GUIDE:
{voice}

Write 1 post ≤ 260 chars, punchy, one insight + CTA about "{args.title}". No hashtags."""
    xpost = chat(x_system, x_user)

    # Save
    slug = f"{args.date}-{slugify(args.title)}"
    blog_dir   = Path(args.out_blog);   blog_dir.mkdir(parents=True, exist_ok=True)
    social_dir = Path(args.out_social); social_dir.mkdir(parents=True, exist_ok=True)

    (blog_dir / f"{slug}.mdx").write_text(mdx.strip() + "\n", encoding="utf-8")
    (social_dir / f"{slug}.linkedin.txt").write_text(linkedin.strip() + "\n", encoding="utf-8")
    (social_dir / f"{slug}.x.txt").write_text(xpost.strip() + "\n", encoding="utf-8")

    print("Wrote:")
    print(f"  {blog_dir / f'{slug}.mdx'}")
    print(f"  {social_dir / f'{slug}.linkedin.txt'}")
    print(f"  {social_dir / f'{slug}.x.txt'}")

if __name__ == "__main__":
    main()
