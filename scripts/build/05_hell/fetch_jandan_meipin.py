# NOTE: 本脚本为公开仓库导出时调整过的构建期参考实现，语料目录已改为仓库相对路径
#       （05_hell/）；运行前请先把原始数据放到 corpora/05_hell/raw/。
# -*- coding: utf-8 -*-
"""抓取煎蛋「没品笑话集 / 一些没品笑话」文章，提取中文笑话段落。"""
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

POSTS = {
    "一些没品笑话": "https://jandan.net/p/114534/",
    "没品笑话集：今天我给90岁的奶奶讲了一个笑话": "https://jandan.net/p/114608/",
    "没品笑话集：我老婆让我收拾东西滚出这个家": "https://jandan.net/p/114739/",
    "没品笑话集：我在钱包里放了一张老婆的照片": "https://jandan.net/p/114940/",
    "没品笑话集：有时候我会觉得身边都是傻X": "https://jandan.net/p/118540/",
    "没品笑话集：我老婆抱怨家里的吸尘器坏了": "https://jandan.net/p/118088/",
}


def main() -> None:
    all_items = []
    for title, url in POSTS.items():
        r = requests.get(url, proxies=PX, headers=HDR, timeout=60)
        soup = BeautifulSoup(r.text, "html.parser")
        blocks = soup.find_all("blockquote")
        print(title, r.status_code, "blocks:", len(blocks))
        for bq in blocks:
            text = bq.get_text(" ", strip=True)
            # 双语：中文在前，取中文句（到第一个英文长句前）
            text = re.split(r"\s(?=[A-Za-z][A-Za-z ,.'’\"-]{25,})", text)[0]
            text = re.sub(r"--[\w.-]+$", "", text).strip()
            text = re.sub(r"\s+", " ", text)
            if len(text) < 12:
                continue
            all_items.append({"source_title": title, "source_url": url, "text": text})
    out = RAW / "jandan_meipin.json"
    out.write_text(json.dumps(all_items, ensure_ascii=False, indent=1), encoding="utf-8")
    print("total", len(all_items))


if __name__ == "__main__":
    main()
