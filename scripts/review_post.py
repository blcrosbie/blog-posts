#!/usr/bin/env python3
import argparse, os, subprocess, sys, difflib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BLOG = REPO / "blog-posts" / "blog"
RAW  = REPO / "corpus" / "blog" / "raw"

def open_in_editor(path: Path):
    editor = os.getenv("EDITOR")
    if editor:
        subprocess.run([editor, str(path)])
        return
    if sys.platform.startswith("win"):
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)])
    else:
        subprocess.run(["xdg-open", str(path)])

def unified_diff(a: str, b: str, fromfile: str, tofile: str) -> str:
    lines = difflib.unified_diff(
        a.splitlines(True), b.splitlines(True),
        fromfile=fromfile, tofile=tofile, lineterm=""
    )
    return "".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="e.g. 2023-08-18-some-title")
    ap.add_argument("--diff", action="store_true", help="Show diff vs raw")
    ap.add_argument("--open", action="store_true", help="Open in editor")
    args = ap.parse_args()

    blog = BLOG / f"{args.slug}.mdx"
    raw  = RAW  / f"{args.slug}.md"

    if not blog.exists():
        print(f"Missing: {blog}")
        sys.exit(1)
    if args.diff:
        if not raw.exists():
            print(f"No raw copy to diff against: {raw}")
            sys.exit(1)
        print(unified_diff(raw.read_text(encoding="utf-8"),
                           blog.read_text(encoding="utf-8"),
                           str(raw), str(blog)))
        return
    if args.open:
        open_in_editor(blog)
        return
    # default: show a preview to stdout
    print(blog.read_text(encoding="utf-8"))

if __name__ == "__main__":
    main()
