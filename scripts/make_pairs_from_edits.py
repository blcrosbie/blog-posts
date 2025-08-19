#!/usr/bin/env python3
import json, hashlib, argparse
from pathlib import Path
from datetime import datetime

REPO = Path(__file__).resolve().parents[1]
BLOG = REPO / "blog-posts" / "blog"
RAW  = REPO / "corpus" / "blog" / "raw"

def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "training" / "pairs.jsonl"))
    ap.add_argument("--min-age-mins", type=int, default=0, help="Optional filter by mtime delta")
    args = ap.parse_args()

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open("w", encoding="utf-8") as fout:
        for raw_md in RAW.glob("*.md"):
            slug = raw_md.stem
            blog_mdx = BLOG / f"{slug}.mdx"
            meta = RAW / f"{slug}.meta.json"
            if not blog_mdx.exists(): continue

            raw_txt  = raw_md.read_text(encoding="utf-8")
            blog_txt = blog_mdx.read_text(encoding="utf-8")
            if raw_txt == blog_txt:  # unchanged
                continue

            meta_obj = {}
            if meta.exists():
                try:
                    meta_obj = json.loads(meta.read_text(encoding="utf-8"))
                except Exception:
                    pass

            rec = {
                "id": f"{slug}-{sha(raw_txt+blog_txt)}",
                "created": datetime.utcnow().isoformat() + "Z",
                "meta": meta_obj,
                "instruction": "Rewrite the draft MDX to final voice with same facts and structure.",
                "input": {
                    "draft_mdx": raw_txt,
                    "voice_dials": meta_obj.get("voice_dials", {}),
                    "notes": "Keep headings/code. Fix clarity, tighten tone, preserve facts."
                },
                "output": blog_txt
            }
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    print(f"Wrote {count} pair(s) to {out}")

if __name__ == "__main__":
    main()
