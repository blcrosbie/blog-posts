#!/usr/bin/env python3
# Usage:
#   python scripts/to_jsonl.py examples > dataset.jsonl
# Each example file should be JSON: {"system":"...", "user":"...", "assistant":"..."}
import sys
import json
from pathlib import Path

def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("examples")
    if not src.exists():
        raise SystemExit(f"Directory not found: {src}")

    rows = []
    for fp in sorted(src.glob("*.json")):
        try:
            ex = json.loads(fp.read_text(encoding="utf-8"))
            rows.append({
                "messages": [
                    {"role": "system", "content": ex.get("system", "")},
                    {"role": "user", "content": ex.get("user", "")},
                    {"role": "assistant", "content": ex.get("assistant", "")},
                ]
            })
        except Exception as e:
            print(f"Skip {fp.name}: {e}", file=sys.stderr)

    sys.stdout.write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))

if __name__ == "__main__":
    main()
