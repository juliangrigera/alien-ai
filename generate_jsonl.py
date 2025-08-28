#!/usr/bin/env python3
# generate_jsonl.py
#
# Usage:
  # python generate_jsonl.py \
  #   --urls urls.txt \
  #   --out batch_input.jsonl \
  #   --model gpt-4o-mini # or your batch-capable model/deployment
#
# Notes:
# - One JSONL line per image (single request that returns all dimensions + overall_gut).
# - Edit DIMENSIONS below to match your 6 dimensions. 'overall_gut' is added automatically.
# - The file produced is ready to upload to the Files API and then create a Batch.
#
# Batch JSONL shape (per line):
# {"custom_id": "...", "method":"POST","url":"/v1/responses","body":{...}}
#
# Docs:
# - Batch API format: https://platform.openai.com/docs/guides/batch  :contentReference[oaicite:0]{index=0}
# - Cookbook example (JSONL lines with method/url/body): https://cookbook.openai.com/examples/batch_processing  :contentReference[oaicite:1]{index=1}
# - Structured Outputs (json_schema): https://platform.openai.com/docs/guides/structured-outputs  :contentReference[oaicite:2]{index=2}

import argparse, json, pathlib, re
from datetime import datetime

# ====== EDIT THIS if you want different dimensions ======
# Provide exactly the 6 you’re using in your current pipeline.
DIMENSIONS = [
    "aesthetics",
    "level_of_detail",
    "utility_for_designer",
    "orderliness",
    "complexity",
    "overall",
]
# ========================================================

PROMPT = (
    "Rate screenshots on three 1–10 integer scales:"
    "1. Aesthetic — visual quality based on layout, color, typography, and polish.Avoid high scores for flat or noisy designs."
    "2. Level of Detail — richness and structure of components, organization. Be forgiving with sparse drafts; lightly penalize repetition."
    "3. Utility for Designers — usefulness for design inspiration, based on aesthetic+detail but adjusted for clarity and layout richness."
    "4. Orderliness — how orderly the UI appears."
    "5. Complexity - how visually complex the UI appears in the screenshot"
    "6. Overall - rate the website design on a 10 point scale"
    "Return only numbers (no explanations)."
)
 
def safe_stem_from_url(url: str) -> str:
    # Try to derive a short stable id from the URL (bucket/path/filename or hash-y fallback)
    stem = url.strip().split("?")[0].split("/")[-1] or "image"
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem)
    return stem[:60]  # keep it short

def build_json_schema(dimensions):
    props = {}
    for d in dimensions:
         props[d] = {"type": "integer", "minimum": 1, "maximum": 10}
    return {
      "type": "object",
      "additionalProperties": False,
      "properties": props,
      "required": list(props.keys()),
    }

def make_request_line(idx, url, model="gpt-4o-mini", temperature=0.2):
    custom_id = f"ui-{idx:05d}-{safe_stem_from_url(url)}"
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": PROMPT},
                    {"type": "input_image", "image_url": url.strip()}
                ]
            }
        ],
        "text": {
          "format": {
            "type": "json_schema",
            "name": "UIRatings",
            "strict": True,
            "schema": build_json_schema(DIMENSIONS)
          }
        },
        # "text": {
        #    "format": {
        #        "type": "json_schema",
        #        "name": "UIRatings",
        #        "schema": build_json_schema(DIMENSIONS),
        #        "strict": True
        #    }
        # },
        "temperature": temperature,
        "max_output_tokens": 400
    }
    return {"custom_id": custom_id, "method": "POST", "url": "/v1/responses", "body": body}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", required=True, help="Text file with one image URL per line.")
    ap.add_argument("--out", required=True, help="Output JSONL path.")
    ap.add_argument("--model", default="gpt-4o", help="Batch-capable model/deployment name.")
    ap.add_argument("--temperature", type=float, default=0.2)
    args = ap.parse_args()

    urls = [ln.strip() for ln in pathlib.Path(args.urls).read_text().splitlines() if ln.strip()]
    if not urls:
        raise SystemExit("No URLs found.")

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        for i, url in enumerate(urls, start=1):
            line = make_request_line(i, url, args.model, args.temperature)
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    print(f"Wrote {len(urls)} lines to {out_path} at {datetime.now().isoformat(timespec='seconds')}.")

if __name__ == "__main__":
    main()
