#!/bin/sh
echo "Preparing posts…"
python3 scripts/prepare_posts.py --root blog || exit 1