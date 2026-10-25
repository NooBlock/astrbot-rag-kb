# NOTE: 本脚本为公开仓库导出时调整过的构建期参考实现，语料目录已改为仓库相对路径
#       （03_ruozhiba/）；运行前请先把原始数据放到 corpora/03_ruozhiba/raw/。
# -*- coding: utf-8 -*-
"""下载弱智吧候选数据源到 raw/，并检测可用性。"""
import os
import json
import sys
from pathlib import Path

import requests

PROXIES = (
    {"http": os.environ["HTTP_PROXY"], "https": os.environ.get("HTTPS_PROXY") or os.environ["HTTP_PROXY"]}
    if os.environ.get("HTTP_PROXY")
    else None
)
OUT = Path(__file__).resolve().parents[2] / "corpora" / "03_ruozhiba" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

CANDIDATES = [
    ("kirp/ruozhiba-raw", "wisdomBar_raw.csv"),
    ("LooksJuicy/ruozhiba", "ruozhiba_qa.json"),
    ("AI-ModelScope/ruozhiba", None),
]


def hf_files(repo: str):
    url = f"https://huggingface.co/api/datasets/{repo}"
    r = requests.get(url, proxies=PROXIES, timeout=60)
    print(f"[api] {repo}: {r.status_code}")
    if r.status_code != 200:
        return None
    data = r.json()
    siblings = [s["rfilename"] for s in data.get("siblings", [])]
    print("  files:", siblings)
    return siblings


def fetch_hf(repo: str, name: str) -> None:
    url = f"https://huggingface.co/datasets/{repo}/resolve/main/{name}"
    dest = OUT / f"{repo.replace('/', '__')}__{name}"
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[skip] {dest.stat().st_size} bytes")
        return
    r = requests.get(url, proxies=PROXIES, timeout=180, allow_redirects=True)
    if r.status_code != 200:
        print(f"[fail] {url}: {r.status_code} {r.text[:200]}")
        return
    dest.write_bytes(r.content)
    print(f"[ok] {dest.name}: {len(r.content)} bytes")


if __name__ == "__main__":
    for repo, fname in CANDIDATES[:2]:
        files = hf_files(repo)
        if files is None:
            continue
        want = fname if fname in files else files[0]
        for f in files:
            if f.endswith((".csv", ".json", ".jsonl", ".parquet", ".txt")):
                print(f"[note] {repo} has {f}")
    # 逐个下载已知文件名
    for name in ("wisdomBar_raw.csv",):
        fetch_hf("kirp/ruozhiba-raw", name)
    for name in ("ruozhiba_qa.json", "ruozhiba_qa.jsonl", "ruozhiba.json", "train.json"):
        fetch_hf("LooksJuicy/ruozhiba", name)
