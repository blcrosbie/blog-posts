#!/usr/bin/env python3
import os, re, json, textwrap
from pathlib import Path
from datetime import datetime, UTC
import argparse
import requests
from typing import Dict, Any, Tuple, Optional

# ---------- Config ----------
REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "corpus"
DEFAULT_CATEGORIES = ["youtube", "linkedin", "other"]
CLEAN_DIR_NAME = "clean"
RAW_OUT_DIR = CORPUS_ROOT / "blog" / "raw"
BLOG_OUT_DIR = REPO_ROOT / "blog"   # your submodule target
SOC_OUT_DIR = REPO_ROOT / "social"  # social text target
VOICE_PATH = REPO_ROOT / "prompts" / "VOICE_GUIDE.yaml"

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# ---------- Helpers ----------
def _label(item) -> str:
    # Robust, readable label for display
    if hasattr(item, "stem"):
        return getattr(item, "stem")
    if hasattr(item, "name"):
        return getattr(item, "name")
    try:
        return Path(item).stem  # string paths
    except Exception:
        return str(item)

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"(^-|-$)", "", s)

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def write_text(p: Path, txt: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")

def choose_from_list(items, prompt="Choose:", allow_search=True) -> int:
    """
    Print a list, optionally filter with /search, and return the ORIGINAL index
    of the chosen item (even after filtering). Accepts Path or str.
    """
    if not items:
        raise SystemExit("No items found.")

    indexed = list(enumerate(items))   # preserve original indices
    filtered = indexed                 # list[(idx, item)]

    while True:
        print()
        for orig_idx, it in filtered:
            print(f"[{orig_idx}] {_label(it)}")

        raw = input(
            f"\n{prompt} (index"
            + (", /search" if allow_search else "")
            + ", or q to cancel): "
        ).strip()

        if raw.lower() in {"q", "quit", "exit"}:
            raise SystemExit("Canceled.")

        if allow_search and raw.startswith("/"):
            q = raw[1:].strip().lower()
            filtered = [(i, it) for i, it in indexed if q in _label(it).lower()]
            if not filtered:
                print(f"No matches for '{q}'. Showing all.")
                filtered = indexed
            continue

        if raw.isdigit():
            idx = int(raw)
            if 0 <= idx < len(items):
                return idx
            print(f"Index {idx} out of range 0..{len(items)-1}")
            continue

        print("Enter a valid index or use /search ...")

def apply_dial_overrides(dials: dict, overrides: list[str]) -> dict:
    """Mutate & return dials with CLI overrides like ['Skepticism=7', 'DryHumor=5']."""
    for item in overrides:
        if "=" not in item:
            print(f"Warning: ignoring malformed --dial '{item}' (expected Key=Value)")
            continue
        key, val = item.split("=", 1)
        key = key.strip()
        sval = val.strip()
        # coerce to int/float when possible
        if re.fullmatch(r"-?\d+", sval):
            val_coerced = int(sval)
        elif re.fullmatch(r"-?\d+\.\d+", sval):
            val_coerced = float(sval)
        else:
            val_coerced = sval
        dials[key] = val_coerced
    return dials

def load_voice(path: Path) -> Tuple[str, Dict[str, Any]]:
    """Load YAML or MD, return (flattened_text, dials_dict)."""
    txt = read_text(path)
    dials = {}
    if path.suffix.lower() in {".yml", ".yaml"}:
        try:
            import yaml  # pip install pyyaml
            y = yaml.safe_load(txt) or {}
            # Flatten for prompt:
            flat_parts = []
            for k, v in y.items():
                if isinstance(v, (list, dict)):
                    flat_parts.append(f"{k}:\n{yaml.safe_dump(v, sort_keys=False)}")
                else:
                    flat_parts.append(f"{k}:\n{v}")
            # Extract a ‘Controls’ mapping if present:
            dials = y.get("Controls", {})
            return "\n".join(flat_parts), dials
        except Exception as e:
            print(f"Warning: could not parse YAML ({e}). Using raw text.")
    return txt, dials

def llm_chat(base_url: str, api_key: Optional[str], model: str,
             system: str, user: str, temperature: float, max_tokens: int) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM {resp.status_code}: {resp.text[:800]}")
    data = resp.json()
    return (data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")).strip()

def sanitize_mdx(mdx: str) -> str:
    # kill code fences marked mdx
    mdx = mdx.replace("```mdx", "```")
    # often models forget to close code fences or frontmatter
    # - ensure frontmatter bounded by --- lines
    if mdx.lstrip().startswith("---"):
        # attempt to find the second ---
        parts = mdx.split("\n")
        first = 0
        second = None
        for i in range(1, min(len(parts), 200)):  # frontmatter near top
            if parts[i].strip() == "---":
                second = i
                break
        if second is None:
            # close it ourselves at top
            parts.insert(1, "---")
            mdx = "\n".join(parts)
    # replace em-dashes with comma (safer YAML)
    mdx = mdx.replace("—", ", ")
    return mdx.strip() + "\n"

def build_control_block(dials: Dict[str, Any]) -> str:
    """Turn numeric voice dials into a concise control header the model can parse."""
    if not dials:
        return ""
    ordered = []
    for k in sorted(dials.keys()):
        v = dials[k]
        if isinstance(v, (int, float, str)):
            ordered.append(f"{k}={v}")
    return "VOICE_DIALS: " + ", ".join(ordered)

# ---------- Main flow ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.getenv("LLM_MODEL", "gpt-4o-mini"))
    ap.add_argument("--base-url", default=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    ap.add_argument("--api-key", default=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))
    ap.add_argument("--temperature", type=float, default=float(os.getenv("LLM_TEMPERATURE", "0.6")))
    ap.add_argument("--max-mdx", type=int, default=1200)
    ap.add_argument("--voice", default=str(VOICE_PATH))
    ap.add_argument(
        "--dial",
        action="append",
        default=[],
        help="Override a voice dial, e.g. --dial Skepticism=7 (can be repeated)"
    )

    args = ap.parse_args()

    # 1) DATE
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    date_in = input(f"Post date (YYYY-MM-DD) [default {today}]: ").strip() or today
    try:
        datetime.strptime(date_in, "%Y-%m-%d")
    except ValueError:
        raise SystemExit("Invalid date; use YYYY-MM-DD.")

    # 2) SOURCE SELECTOR
    print("\nSelect a corpus category:")
    cats_on_disk = [c for c in DEFAULT_CATEGORIES if (CORPUS_ROOT / c / CLEAN_DIR_NAME).exists()]
    if not cats_on_disk:
        raise SystemExit(f"No corpus found under {CORPUS_ROOT} (expected youtube/linkedin/other).")
    cat_idx = choose_from_list(cats_on_disk, "Category")
    category = cats_on_disk[cat_idx]
    clean_dir = CORPUS_ROOT / category / CLEAN_DIR_NAME
    docs = sorted([p for p in clean_dir.glob("**/*") if p.suffix.lower() in {".md", ".txt"}])
    print(f"\nSelect a document in: {category}")
    
    idx = choose_from_list(docs, "Document")
    src_path = docs[idx]
    notes = read_text(src_path)

    # 3) TITLE
    custom_title = input("\nCustom title (leave blank to auto-generate): ").strip()
    voice_text, dials = load_voice(Path(args.voice))

    # Apply CLI overrides (create dict if not present)
    dials = dials or {}
    if args.dial:
        apply_dial_overrides(dials, args.dial)

    controls = build_control_block(dials)
    if not custom_title:
        if not args.api_key:
            print("No API key set. Using fallback title from filename.")
            custom_title = re.sub(r"[_\-]+", " ", src_path.stem).title()[:60]
        else:
            custom_title = llm_chat(
                args.base_url, args.api_key, args.model,
                "Return only a concise blog title (≤8 words). No quotes.",
                f"{controls}\n\nContext:\n{voice_text}\n\nSource excerpt:\n{notes[:4000]}",
                temperature=0.5, max_tokens=30
            ).splitlines()[0].strip().strip('"')
    print(f"Title: {custom_title}")

    # 4) Build prompts
    system = "You are Brandon Crosbie’s writing partner. Output only valid MDX."
    user = textwrap.dedent(f"""
    {controls}

    VOICE_GUIDE:
    {voice_text}

    Create a 1200–1600 word MDX blog post with frontmatter:
    ---
    title: "{custom_title}"
    date: "{date_in}"
    excerpt: (one sentence)
    tags: [data-science, python, ai, machine-learning]
    hero: "/images/bulb-icon.png"
    ---
    Rules:
    - Use only MDX/Markdown (no JSX components)
    - Headings with ## / ###
    - Short paragraphs, code fences with language tags
    - Ground all claims only in SOURCE (if unsure, hedge)

    SOURCE:
    {notes}
    """)

    # 5) Generate content
    if not args.api_key:
        raise SystemExit("Set LLM_API_KEY or OPENAI_API_KEY to generate content.")

    mdx = llm_chat(args.base_url, args.api_key, args.model, system, user,
                   temperature=args.temperature, max_tokens=args.max_mdx)
    mdx = sanitize_mdx(mdx)

    bullets = llm_chat(
        args.base_url, args.api_key, args.model,
        "Summarize for social drafting. Output 4–6 bullets, total ≤ 600 chars.",
        mdx[:6000],
        temperature=0.4, max_tokens=200
    )
    linkedin = llm_chat(
        args.base_url, args.api_key, args.model,
        "You are Brandon writing for LinkedIn.",
        f"""{controls}

VOICE_GUIDE:
{voice_text}

Write a 900–1100 character LinkedIn post teeing up the blog "{custom_title}".
Use the bullets verbatim where it helps.
Structure: 1 clean hook, 2 short paragraphs (stat + trade-off), 3–5 bullets, grounded CTA. Max 3 hashtags.
BULLETS:
{bullets}""",
        temperature=0.6, max_tokens=700
    )
    xpost = llm_chat(
        args.base_url, args.api_key, args.model,
        "You are Brandon posting to X. One post ≤ 40 tokens or more specifically ≤ 260 characters, dry/skeptical quip allowed. No hashtags.",
        f"{controls}\n\nContext:\n{voice_text}\n\nTitle: {custom_title}\n\nKey bullets:\n{bullets}",
        temperature=0.6, max_tokens=260
    )

    # Remove the notorious emdash
    mdx = mdx.replace('—', ', ')
    linkedin = linkedin.replace('—', ', ')
    xpost = xpost.replace('—', ', ')

    mdx = mdx.replace("’", "'")
    linkedin = linkedin.replace("’", "'")
    xpost = xpost.replace("’", "'")

    # get the first mdx fence backticks
    mdx = mdx.replace('```mdx', '')

    # get the last 3 fence backticks ```
    if mdx.endswith('```'):
        mdx = mdx[:-3]
        mdx = mdx + '---'

    if not mdx.endswith('---'):
        mdx = mdx + '\n---'

    

    # 6) Save outputs
    slug = f"{date_in}-{slugify(custom_title)}"
    blog_path = BLOG_OUT_DIR / f"{slug}.mdx"
    soc_ln = SOC_OUT_DIR / f"{slug}.linkedin.txt"
    soc_x  = SOC_OUT_DIR / f"{slug}.x.txt"
    raw_path = RAW_OUT_DIR / f"{slug}.md"
    meta_path = RAW_OUT_DIR / f"{slug}.meta.json"

    write_text(blog_path, mdx)
    write_text(soc_ln, linkedin.strip() + "\n")
    write_text(soc_x,  xpost.strip() + "\n")
    write_text(raw_path, mdx)  # save generated text to raw
    write_text(meta_path, json.dumps({
        "title": custom_title,
        "date": date_in,
        "slug": slug,
        "source_path": str(src_path.relative_to(REPO_ROOT)),
        "category": category,
        "model": args.model,
        "base_url": args.base_url,
        "voice_file": str(Path(args.voice).relative_to(REPO_ROOT)),
        "voice_dials": dials,
        "created_utc": datetime.now(UTC).isoformat() + "Z",
    }, indent=2))

    print("\nWrote:")
    print(f"  {blog_path}")
    print(f"  {soc_ln}")
    print(f"  {soc_x}")
    print(f"  {raw_path}")
    print(f"  {meta_path}")
    print("\nNext:")
    print("  - Review/edit blog/*.mdx")
    print("  - Keep raw/*.md as the pristine generated copy for training pairs later")
    print("  - Commit when happy")
if __name__ == "__main__":
    main()
