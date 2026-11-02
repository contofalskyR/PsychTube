#!/usr/bin/env python3
"""Decode a saved browser-pane tool result (JSON array with {type,text}) that carries
{"part": n, "b64": "<base64>"} (optionally gzip'd payload) into a file.

usage: decode_chunk.py <tool-result-file> <out-file> [--gunzip]
"""
import base64
import gzip
import json
import re
import sys


def extract(path: str) -> dict:
    raw = json.load(open(path))
    text = raw[0]["text"] if isinstance(raw, list) else raw["text"]
    # strip trailing "(captured at origin ...)" note and any truncation marker
    cut = text.rfind("\n}")
    if cut == -1:
        raise SystemExit("no JSON object end found in %s" % path)
    obj = json.loads(text[: cut + 2])
    return obj


def main():
    src, dst = sys.argv[1], sys.argv[2]
    gunzip = "--gunzip" in sys.argv
    obj = extract(src)
    b64 = obj["b64"]
    if "…[truncated" in b64:
        raise SystemExit("payload truncated by bridge; shrink chunk size")
    data = base64.b64decode(b64)
    if gunzip:
        data = gzip.decompress(data)
    with open(dst, "wb") as f:
        f.write(data)
    print("part", obj.get("part"), "->", dst, len(data), "bytes")


if __name__ == "__main__":
    main()
