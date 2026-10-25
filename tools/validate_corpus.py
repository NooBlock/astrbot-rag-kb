"""校验语料目录是否符合 rag_corpora/SPEC.md 的约定。

用法::

    python validate_corpus.py <corpus_dir> [--min 50] [--max-text 1200]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def validate(corpus_dir: Path, min_chunks: int = 50, max_text: int = 1200) -> int:
    errors: list[str] = []
    chunks_path = corpus_dir / "chunks.jsonl"
    manifest_path = corpus_dir / "manifest.json"

    if not chunks_path.exists():
        print(f"[FAIL] 缺少 {chunks_path}")
        return 1
    if not manifest_path.exists():
        print(f"[FAIL] 缺少 {manifest_path}")
        return 1

    texts: list[str] = []
    with chunks_path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"第 {lineno} 行 JSON 非法: {exc}")
                continue
            if not isinstance(item, dict):
                errors.append(f"第 {lineno} 行不是对象")
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                errors.append(f"第 {lineno} 行 text 为空")
                continue
            if len(text) > max_text:
                errors.append(f"第 {lineno} 行 text 过长: {len(text)} 字符")
            texts.append(text)

    dup = len(texts) - len(set(texts))
    if dup:
        errors.append(f"存在 {dup} 条完全重复的 text")

    if len(texts) < min_chunks:
        errors.append(f"条数 {len(texts)} 少于下限 {min_chunks}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in ("kb_name", "description", "emoji", "source_url", "num_chunks"):
        if key not in manifest:
            errors.append(f"manifest 缺少字段 {key}")
    if manifest.get("num_chunks") != len(texts):
        errors.append(f"manifest.num_chunks={manifest.get('num_chunks')} 与实际 {len(texts)} 不一致")

    print(f"目录: {corpus_dir}")
    print(f"条数: {len(texts)}")
    if texts:
        lens = [len(t) for t in texts]
        print(f"长度: min={min(lens)} avg={sum(lens)//len(lens)} max={max(lens)}")
    print(f"kb_name: {manifest.get('kb_name')!r}")

    if errors:
        print("\n[FAIL] 发现问题:")
        for err in errors[:30]:
            print("  -", err)
        return 1
    print("\n[OK] 校验通过")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_dir", nargs="?", default=None)
    parser.add_argument("--all", metavar="ROOT", default=None, help="校验 ROOT 下所有语料目录")
    parser.add_argument("--min", type=int, default=50)
    parser.add_argument("--max-text", type=int, default=1200)
    args = parser.parse_args()

    if args.all:
        root = Path(args.all)
        dirs = sorted(p for p in root.iterdir() if p.is_dir() and (p / "chunks.jsonl").exists())
        if not dirs:
            print(f"[FAIL] {root} 下没有找到含 chunks.jsonl 的语料目录")
            sys.exit(1)
        failed = 0
        total = 0
        for corpus_dir in dirs:
            print("=" * 60)
            code = validate(corpus_dir, args.min, args.max_text)
            failed += 1 if code else 0
            with (corpus_dir / "chunks.jsonl").open(encoding="utf-8") as fh:
                total += sum(1 for line in fh if line.strip())
        print("=" * 60)
        print(f"共 {len(dirs)} 个语料目录，合计 {total} 条 chunk，失败 {failed} 个")
        sys.exit(1 if failed else 0)

    if not args.corpus_dir:
        parser.error("需要 corpus_dir，或使用 --all <corpora 目录>")
    sys.exit(validate(Path(args.corpus_dir), args.min, args.max_text))


if __name__ == "__main__":
    main()
