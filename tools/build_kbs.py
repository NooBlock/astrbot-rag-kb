"""把 rag_corpora 下的语料导入 AstrBot 知识库。

行为：
1. 扫描 01_* ~ 06_* 目录下的 chunks.jsonl + manifest.json；
2. 按 manifest.kb_name 在 AstrBot 中查找知识库，不存在则创建；
3. 分片调用 /documents/import（预切块），轮询任务直到完成；
4. 用 /stats 校验文档数与 chunk 数，并写入 _state/imported.json。

用法::

    python build_kbs.py --create-only          # 只建库，不导入
    python build_kbs.py --only 01_cheer_terms  # 只处理指定目录
    python build_kbs.py                        # 全量导入（可重复执行，已导入的会跳过）
    python build_kbs.py --force                # 忽略状态，重新导入（先删除同名库）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kb_client import KBClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO_ROOT / "corpora"

# manifest 缺失时的兜底元数据
FALLBACK_META = {
    "01_cheer_terms": ("网络流行语释义库", "🗣️", "近年中文网络流行语/黑话的精确释义库（Cheer / SCUNLP-Buzzword），适合回答「xx 是什么意思」。"),
    "02_meme_style": ("网梗对话风格库", "💬", "抖音/小红书/B站评论区真实玩梗对话（zh-meme-sft-8k），用于学习梗的用法与语气。"),
    "03_ruozhiba": ("弱智吧语料库", "🧠", "弱智吧经典问答与标题，提供无厘头/反差幽默风格参考。"),
    "04_vbar": ("V吧黑话库", "🎭", "V 圈 / V 吧黑话与圈层用语精标词条，理解特定社区语境。"),
    "05_hell": ("地狱笑话库", "💀", "中文黑色幽默 / 地狱笑话精标语料，附使用边界提示。"),
    "06_bili_terms": ("B站热词图鉴", "📺", "B 站热词 / 名词解释，动态补充站内新梗。"),
}


def load_state(state_path: Path) -> dict:
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {}


def save_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_corpus(corpus_dir: Path) -> dict | None:
    chunks_path = corpus_dir / "chunks.jsonl"
    manifest_path = corpus_dir / "manifest.json"
    if not chunks_path.exists():
        return None
    chunks: list[str] = []
    with chunks_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            text = (item.get("text") or "").strip()
            if text:
                chunks.append(text)
    if not chunks:
        return None
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fallback = FALLBACK_META.get(corpus_dir.name, (corpus_dir.name, "📚", ""))
    return {
        "dir": corpus_dir,
        "chunks": chunks,
        "sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
        "kb_name": manifest.get("kb_name") or fallback[0],
        "emoji": manifest.get("emoji") or fallback[1],
        "description": manifest.get("description") or fallback[2],
        "source_url": manifest.get("source_url", ""),
        "source_license": manifest.get("source_license", ""),
    }


def find_kb(client: KBClient, kb_name: str) -> dict | None:
    for item in client.list_kbs()["items"]:
        if item["kb_name"] == kb_name:
            return item
    return None


def ensure_kb(client: KBClient, corpus: dict, provider_id: str) -> dict:
    existing = find_kb(client, corpus["kb_name"])
    if existing:
        if existing.get("description") != corpus["description"]:
            try:
                client.update_kb(
                    existing["kb_id"],
                    corpus["kb_name"],
                    corpus["description"],
                    corpus["emoji"],
                )
                existing["description"] = corpus["description"]
            except Exception as exc:
                print(f"  (说明同步失败，忽略: {exc})", flush=True)
        return existing
    print(f"  -> 创建知识库 {corpus['kb_name']!r} ...", flush=True)
    client.create_kb(
        corpus["kb_name"],
        corpus["description"],
        embedding_provider_id=provider_id,
        emoji=corpus["emoji"],
    )
    existing = find_kb(client, corpus["kb_name"])
    if not existing:
        raise RuntimeError(f"创建后仍找不到知识库 {corpus['kb_name']}")
    return existing


def delete_kb_retry(client: KBClient, kb_id: str, attempts: int = 6) -> None:
    """Delete a knowledge base, retrying transient Windows file locks.

    Args:
        client: AstrBot API client.
        kb_id: Knowledge base id to delete.
        attempts: Maximum attempts before re-raising.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            client.delete_kb(kb_id)
            return
        except Exception as exc:  # WinError 32: file still locked by the server
            last_error = exc
            print(f"  -> 删除库失败（第 {attempt}/{attempts} 次），3 秒后重试: {str(exc)[:160]}", flush=True)
            time.sleep(3)
    raise RuntimeError(f"多次重试仍无法删除知识库 {kb_id}: {last_error}")


def import_corpus(client: KBClient, corpus: dict, kb: dict) -> dict:
    chunks = corpus["chunks"]
    print(f"  -> 导入 {len(chunks)} 条 chunk 到 {corpus['kb_name']!r} ({kb['kb_id']})", flush=True)
    t0 = time.time()
    results = client.upload_chunks(
        kb["kb_id"],
        f"{corpus['kb_name']}.txt",
        chunks,
        shard_size=800,
        batch_size=32,
        tasks_limit=3,
        max_retries=3,
        timeout=3600,
    )
    elapsed = round(time.time() - t0, 1)
    for res in results:
        result = res.get("result") or {}
        if res.get("status") != "completed" or result.get("failed"):
            raise RuntimeError(f"导入失败: {res}")
    return {
        "kb_id": kb["kb_id"],
        "kb_name": corpus["kb_name"],
        "source_url": corpus["source_url"],
        "source_license": corpus["source_license"],
        "num_chunks": len(chunks),
        "num_docs": len(results),
        "elapsed_seconds": elapsed,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def verify(client: KBClient, corpus: dict, kb: dict) -> dict:
    stats = client.get_stats(kb["kb_id"])
    expected = len(corpus["chunks"])
    print(
        f"  -> 校验 doc_count={stats.get('doc_count')} chunk_count={stats.get('chunk_count')} / 期望 {expected}",
        flush=True,
    )
    if stats.get("chunk_count") != expected:
        raise RuntimeError(
            f"chunk_count={stats.get('chunk_count')} 与期望 {expected} 不一致（可能存在孤儿 chunk）"
        )
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="", help="逗号分隔的目录名")
    parser.add_argument("--create-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="语料根目录（默认：仓库根下的 corpora/）",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="AstrBot 的 cmd_config.json 路径（也可用环境变量 ASTRBOT_CONFIG）",
    )
    parser.add_argument(
        "--embedding-provider-id",
        default="openai_embedding",
        help="新建知识库时使用的 embedding provider id（默认 openai_embedding）",
    )
    args = parser.parse_args()

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"语料根目录不存在: {root}")
        return 1
    state_path = root / "_state" / "imported.json"
    dirs = sorted(p for p in root.iterdir() if p.is_dir() and p.name[:2].isdigit())
    if only:
        dirs = [p for p in dirs if p.name in only]

    client = KBClient(config_path=args.config)
    state = load_state(state_path)
    summary = []

    for corpus_dir in dirs:
        corpus = load_corpus(corpus_dir)
        if not corpus:
            print(f"[skip] {corpus_dir.name}: 没有 chunks.jsonl 或内容为空")
            continue
        print(f"[{corpus_dir.name}] kb_name={corpus['kb_name']!r} chunks={len(corpus['chunks'])}")
        kb = None
        try:
            kb = ensure_kb(client, corpus, args.embedding_provider_id)
            if args.create_only:
                summary.append({"dir": corpus_dir.name, "kb_name": corpus["kb_name"], "kb_id": kb["kb_id"], "created": True})
                continue
            recorded = state.get(corpus_dir.name, {})
            if (
                not args.force
                and recorded.get("num_chunks") == len(corpus["chunks"])
                and recorded.get("sha256") == corpus["sha256"]
            ):
                print("  -> 状态记录显示已导入（内容哈希一致），跳过（--force 可重建）")
            else:
                if recorded or args.force:
                    # 直接删除并重建知识库，避免 delete_document 在 doc.db 中遗留孤儿 chunk
                    old = find_kb(client, corpus["kb_name"])
                    if old:
                        print(f"  -> 删除旧库 {old['kb_id']} 后重建（{recorded.get('num_chunks') if recorded else '?'} -> {len(corpus['chunks'])}）")
                        delete_kb_retry(client, old["kb_id"])
                        kb = ensure_kb(client, corpus, args.embedding_provider_id)
                state[corpus_dir.name] = {**import_corpus(client, corpus, kb), "sha256": corpus["sha256"]}
                save_state(state_path, state)
            stats = verify(client, corpus, kb)
            summary.append({**state.get(corpus_dir.name, {}), "stats": stats})
        except Exception as exc:
            print(f"  !! 失败: {type(exc).__name__}: {exc}")
            summary.append({"dir": corpus_dir.name, "kb_name": corpus["kb_name"], "error": str(exc)})

    print("\n==== 汇总 ====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all("error" not in item for item in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
