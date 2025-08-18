#!/usr/bin/env python3
import argparse
import os
import re
import json
from pathlib import Path
import requests
from datetime import datetime
from slugify import slugify

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"(^-|-$)", "", s)
    return s

def chat(system: str, user: str, *, base_url: str, api_key: str|None, model: str,
         temperature: float, max_tokens: int) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(
            f"LLM error {resp.status_code} from {url}\n"
            f"model='{model}' base_url='{base_url}'\n"
            f"Body: {resp.text[:800]}"
        )
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise RuntimeError(f"Unexpected LLM response schema: {e}\n{json.dumps(data)[:800]}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("title")
    ap.add_argument("date", help="YYYY-MM-DD")
    ap.add_argument("source_md_path", help="Cleaned markdown transcript")
    ap.add_argument("--voice", default="prompts/VOICE_GUIDE.md")
    ap.add_argument("--out-blog", default="blog")
    ap.add_argument("--out-social", default="social")
    ap.add_argument("--model", default=os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")))
    ap.add_argument("--base-url", default=os.getenv("LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")))
    ap.add_argument("--api-key", default=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY")))
    ap.add_argument("--max-output-tokens", type=int, default=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1200")))
    ap.add_argument("--temperature", type=float, default=float(os.getenv("LLM_TEMPERATURE", "0.7")))
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

    # 1) MDX
    mdx = chat(
        "You are Brandon Crosbie’s writing partner. Output only valid MDX.",
        f"""VOICE_GUIDE:
{voice}

Create a 1200–1600 word MDX blog post with frontmatter:
---
title: "{args.title}"
date: "{args.date}"
excerpt: (one sentence)
tags: []
hero: "/images/bulb-icon.png"
slug: "{slugify(args.title)}"
---

Ground your claims ONLY in the SOURCE below. Use H2/H3 headings, include short callouts and code blocks where useful. No JSX components, just MDX.

SOURCE:
{notes}
""",
        base_url=args.base_url, api_key=args.api_key, model=args.model,
        temperature=args.temperature, max_tokens=args.max_output_tokens
    )

    # 2) bullets
    bullets = chat(
        "Summarize for social drafting.",
        f"Give 4–6 bullets (max ~600 chars total) of the key takeaways from this MDX:\n{mdx[:6000]}",
        base_url=args.base_url, api_key=args.api_key, model=args.model,
        temperature=args.temperature, max_tokens=600
    )

    # 3) LinkedIn
    linkedin = chat(
        "You are Brandon writing for LinkedIn.",
        f"""VOICE_GUIDE:
{voice}

Write a 900–1100 character LinkedIn post teeing up the blog "{args.title}".
Use the bullets verbatim where possible.
Structure: 1 strong hook line, 2–3 short paragraphs, 1 skim list, clear CTA to read the blog.
No more than 3 hashtags at the end.

BULLETS:
{bullets}
""",
        base_url=args.base_url, api_key=args.api_key, model=args.model,
        temperature=args.temperature, max_tokens=700
    )

    # 4) X
    xpost = chat(
        "You are Brandon posting to X.",
        f"""VOICE_GUIDE:
{voice}

Write 1 post ≤ 260 chars, punchy, one insight + CTA about "{args.title}". No hashtags.""",
        base_url=args.base_url, api_key=args.api_key, model=args.model,
        temperature=args.temperature, max_tokens=260
    )

    slug = f"{args.date}-{slugify(args.title)}"
    blog_dir   = Path(args.out_blog);   blog_dir.mkdir(parents=True, exist_ok=True)
    social_dir = Path(args.out_social); social_dir.mkdir(parents=True, exist_ok=True)

    # Remove the notorious emdash
    mdx = mdx.replace('—', ', ')
    linkedin = linkedin.replace('—', ', ')
    xpost = xpost.replace('—', ', ')

    mdx = mdx.replace('```mdx', '')
    mdx = mdx.replace('```', '')

    (blog_dir / f"{slug}.mdx").write_text(mdx.strip() + "\n", encoding="utf-8")
    (social_dir / f"{slug}.linkedin.txt").write_text(linkedin.strip() + "\n", encoding="utf-8")
    (social_dir / f"{slug}.x.txt").write_text(xpost.strip() + "\n", encoding="utf-8")

    print("Wrote:")
    print(f"  {blog_dir / f'{slug}.mdx'}")
    print(f"  {social_dir / f'{slug}.linkedin.txt'}")
    print(f"  {social_dir / f'{slug}.x.txt'}")

if __name__ == "__main__":
    main()
