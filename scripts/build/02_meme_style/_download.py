# NOTE: 本脚本为公开仓库导出时调整过的构建期参考实现，语料目录已改为仓库相对路径
#       （02_meme_style/）；运行前请先把原始数据放到 corpora/02_meme_style/raw/。
# -*- coding: utf-8 -*-
"""下载 GaryYang123/zh-meme-sft-8k 原始数据到 raw/。"""
import os
import sys
from pathlib import Path

import requests

PROXIES = (
    {"http": os.environ["HTTP_PROXY"], "https": os.environ.get("HTTPS_PROXY") or os.environ["HTTP_PROXY"]}
    if os.environ.get("HTTP_PROXY")
    else None
)
BASE = "https://huggingface.co/datasets/GaryYang123/zh-meme-sft-8k/resolve/main/"
OUT = Path(__file__).resolve().parents[2] / "corpora" / "02_meme_style" / "raw"
OUT.mkdir(parents=True, exist_ok=True)


def fetch(name: str) -> None:
    url = BASE + name
    dest = OUT / name
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[skip] {name} already {dest.stat().st_size} bytes")
        return
    r = requests.get(url, proxies=PROXIES, timeout=120, allow_redirects=True)
    r.raise_for_status()
    dest.write_bytes(r.content)
    print(f"[ok] {name}: {len(r.content)} bytes")


if __name__ == "__main__":
    for f in ("train.jsonl", "validation.jsonl"):
        fetch(f)
