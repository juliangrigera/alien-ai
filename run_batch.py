#!/usr/bin/env python3
# run_batch.py
# Usage:
#   export OPENAI_API_KEY=sk-...
#   python run_batch.py --input batch_input.jsonl
# Optional:
#   python run_batch.py --input batch_input.jsonl --window 24h --poll 10
#   python run_batch.py --resume BATCH_ID   # skip upload/create and just poll+download
import os, json
import argparse, time, pathlib, sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TERMINAL = {"completed", "failed", "expired", "cancelled"}

def save_file(client: OpenAI, file_id: str, path: pathlib.Path) -> None:
    stream = client.files.content(file_id)
    data = stream.read()
    path.write_bytes(data)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=False, default="batch_input.jsonl", help="JSONL with batch requests")
    ap.add_argument("--window", default="24h", choices=["24h", "48h"], help="completion_window")
    ap.add_argument("--poll", type=int, default=15, help="poll interval (seconds)")
    ap.add_argument("--resume", help="existing BATCH_ID to resume polling/download")
    ap.add_argument("--out", default=None, help="output filepath for batch results (.jsonl)")
    ap.add_argument("--err", default=None, help="error filepath for failed requests (.jsonl)")
    args = ap.parse_args()

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    input_path = pathlib.Path(args.input)
    if not args.resume:
        if not input_path.exists():
            sys.exit(f"Input file not found: {input_path}")
        print(f"Uploading {input_path} …")
        f = client.files.create(file=open(str(input_path), "rb"), purpose="batch")
        print(f"  file_id: {f.id}")

        print(f"Creating batch (window={args.window}) …")
        b = client.batches.create(
            input_file_id=f.id,
            endpoint="/v1/responses",
            completion_window=args.window,
        )
        batch_id = b.id
    else:
        batch_id = args.resume
        print(f"Resuming batch {batch_id} …")
        b = client.batches.retrieve(batch_id)

    # default output/err names
    stem = input_path.stem if input_path.name != "" else "batch"
    out_path = pathlib.Path(args.out or f"{stem}_output.jsonl")
    err_path = pathlib.Path(args.err or f"{stem}_errors.jsonl")

    # poll
    while True:
        b = client.batches.retrieve(batch_id)
        status = getattr(b, "status", "unknown")
        counts = getattr(b, "request_counts", None)
        if counts:
            print(f"[{status}] total={counts.total} completed={counts.completed} failed={counts.failed}")
        else:
            print(f"[{status}]")
        if status in TERMINAL:
            break
        time.sleep(args.poll)

    # download results if any
    if getattr(b, "output_file_id", None):
        print(f"Downloading output to {out_path} …")
        save_file(client, b.output_file_id, out_path)
        n_lines = sum(1 for _ in open(out_path, "r", encoding="utf-8"))
        print(f"Saved {n_lines} lines → {out_path}")

    if getattr(b, "error_file_id", None):
        print(f"Downloading errors to {err_path} …")
        save_file(client, b.error_file_id, err_path)
        print(f"Saved errors → {err_path}")

    print(f"Batch {batch_id} finished with status: {b.status}")

if __name__ == "__main__":
    main()
