# Create and activate a venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Set env (session only). For OSS, point BASE_URL to your server.
$env:LLM_API_KEY="sk-..."                    # or a dummy key if your OSS server ignores it
$env:LLM_MODEL="gpt-oss-20b"
$env:LLM_BASE_URL="https://api.openai.com/v1"  # replace with your vLLM/OpenRouter endpoint

# 1) Clean transcript
python scripts/clean_transcript.py corpus\youtube\raw\2020-qgis-gee-plugin-part-1.txt `
  -o corpus\youtube\clean\2020-qgis-gee-plugin-part-1.md

# 2) Generate MDX + LinkedIn + X (write into submodule paths)
python scripts/make_post.py "QGIS + Google Earth Engine: 92 Feeds, One Plugin" 2020-07-01 `
  corpus\youtube\clean\2020-qgis-gee-plugin-part-1.md `
  --out-blog blog-posts\blog --out-social blog-posts\social
