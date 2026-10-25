"""导入后校验：列出知识库统计，并跑一组检索冒烟测试。

用法::

    python verify_kbs.py
    python verify_kbs.py --query "尊嘟假嘟是什么意思"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kb_client import KBClient  # noqa: E402

DEFAULT_QUERIES = [
    "尊嘟假嘟是什么意思？",
    "什么是独轮车？",
    "狐坦和 fbk 是谁？",
    "B站 666 是什么梗？",
    "地狱笑话：这个笑话为什么好笑？",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", action="append", default=None)
    parser.add_argument(
        "--config",
        default=None,
        help="AstrBot 的 cmd_config.json 路径（也可用环境变量 ASTRBOT_CONFIG）",
    )
    parser.add_argument("--base-url", default=None, help="AstrBot WebUI API 地址")
    args = parser.parse_args()
    queries = args.query or DEFAULT_QUERIES

    client = KBClient(config_path=args.config, base_url=args.base_url)
    kbs = client.list_kbs()["items"]
    print("==== 知识库统计 ====")
    for kb in kbs:
        stats = client.get_stats(kb["kb_id"])
        print(
            f"- {kb['emoji']} {kb['kb_name']:<10} kb_id={kb['kb_id']} "
            f"docs={stats.get('doc_count')} chunks={stats.get('chunk_count')}"
        )

    names = [kb["kb_name"] for kb in kbs]
    if not names:
        print("没有知识库")
        return 1
    anchor = kbs[0]["kb_id"]
    print("\n==== 检索冒烟测试 ====")
    for query in queries:
        result = client.retrieve(anchor, names, query, top_k=3)
        print(f"\nQ: {query}")
        for item in result.get("results", [])[:3]:
            text = (item.get("text") or item.get("content") or "").replace("\n", " ")
            score = item.get("score")
            source = item.get("kb_name") or item.get("kb_id")
            print(f"  [{score}] ({source}) {text[:120]}")
        if not result.get("results"):
            print("  (无命中)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
