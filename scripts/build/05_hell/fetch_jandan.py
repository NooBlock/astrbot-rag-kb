# NOTE: 本脚本为公开仓库导出时调整过的构建期参考实现，语料目录已改为仓库相对路径
#       （05_hell/）；运行前请先把原始数据放到 corpora/05_hell/raw/。
# -*- coding: utf-8 -*-
"""抓取煎蛋「一些地狱笑话」系列文章，提取中文笑话段落。"""
import os
import re
import json
import pathlib

import requests
from bs4 import BeautifulSoup

PX = (
    {"http": os.environ["HTTP_PROXY"], "https": os.environ.get("HTTPS_PROXY") or os.environ["HTTP_PROXY"]}
    if os.environ.get("HTTP_PROXY")
    else None
)
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
RAW = Path(__file__).resolve().parents[2] / "corpora" / "05_hell" / "raw"

ARTICLES = {
    "一些地狱笑话": "https://jandan.net/p/111112/",
    "一些地狱笑话(2)": "https://jandan.net/p/111148/",
    "一些地狱笑话(3)": "https://jandan.net/p/111166/",
    "一些地狱笑话(4)": "https://jandan.net/p/111275/",
}


def clean_zh(s: str) -> str:
    """煎蛋段落是「中文 / English」双语，取中文部分。"""
    s = s.strip()
    # 中文句子在前，英文原文在后；按首个 ASCII 字母占比高的行切分
    lines = [x.strip() for x in s.split("\n") if x.strip()]
    zh = []
    for line in lines:
        # 纯英文行（ASCII 字母占比 > 0.5）视为译文原文
        letters = sum(1 for ch in line if ch.isascii() and ch.isalpha())
        if letters > len(line) * 0.5 and len(line) > 12:
            break
        zh.append(line)
    out = " ".join(zh) if zh else s
    out = re.sub(r"\s+", " ", out).strip()
    return out


def main() -> None:
    all_items = []
    for title, url in ARTICLES.items():
        r = requests.get(url, proxies=PX, headers=HDR, timeout=60)
        raw_path = RAW / (re.sub(r"[^\w]", "_", title) + ".html")
        raw_path.write_text(r.text, encoding="utf-8")
        soup = BeautifulSoup(r.text, "html.parser")
        bqs = soup.find_all("blockquote")
        print(title, r.status_code, "blockquotes:", len(bqs))
        for bq in bqs:
            text = clean_zh(bq.get_text("\n", strip=True))
            if len(text) < 15:
                continue
            all_items.append({"source_title": title, "source_url": url, "text": text})
    out = RAW / "jandan_jokes.json"
    out.write_text(json.dumps(all_items, ensure_ascii=False, indent=1), encoding="utf-8")
    print("total", len(all_items))


if __name__ == "__main__":
    main()
