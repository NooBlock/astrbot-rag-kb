# NOTE: 本脚本为公开仓库导出时调整过的构建期参考实现，语料目录已改为仓库相对路径
#       （01_cheer_terms/）；运行前请先把原始数据放到 corpora/01_cheer_terms/raw/。
# -*- coding: utf-8 -*-
"""构建「网络流行语释义库」语料（Cheer / SCUNLP-Buzzword, ACL 2025）。

数据源: https://raw.githubusercontent.com/SCUNLP/Buzzword/main/data/data.py
字段（见上游 README）:
  examples      -> 例句（列表，仅少量词条有）
  definition    -> 定义（简洁释义）
  ground_truth  -> 流行词介绍（较详细的背景/用法说明）
  *_KEY / *_score 等模型定义与打分 -> 不采用（模型生成，含事实错误）

产物: chunks.jsonl / manifest.json（写入 01_cheer_terms/）
用法: python build_cheer.py
"""

from __future__ import annotations

import os

import ast
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DATA_URL = "https://raw.githubusercontent.com/SCUNLP/Buzzword/main/data/data.py"
PROXIES = (
    {"http": os.environ["HTTP_PROXY"], "https": os.environ.get("HTTPS_PROXY") or os.environ["HTTP_PROXY"]}
    if os.environ.get("HTTP_PROXY")
    else None
)
OUT_DIR = Path(__file__).resolve().parents[2] / "corpora" / "01_cheer_terms"
MAX_LEN = 900          # 超长词条拆分阈值
ATOM_MAX = 400         # 单个原子句最长字符数（超长硬切）
CST = timezone(timedelta(hours=8))

ZW = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff\u2060"), None)
CJK_TAG = re.compile(r"<([^<>\s]{1,20})>")
SENT_END = re.compile(r"(?<=[。！？；!?;…])")
WS = re.compile(r"\s+")


def clean(text: str) -> str:
    """清洗单段文本：去零宽/控制字符、压缩空白、书名号裸尖括号规范化。"""
    if not text:
        return ""
    s = str(text).translate(ZW)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\u3000", " ")
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    s = WS.sub(" ", s).strip()
    # 上游用 <书名> 表示书名号，规范为《书名》，避免被当成 HTML 标签
    s = CJK_TAG.sub(lambda m: f"《{m.group(1)}》", s)
    s = s.replace("<", "‹").replace(">", "›")
    return s.strip()


def build_units(entry: dict) -> list[tuple[str, str]]:
    """按 释义/例句/详解 顺序返回 [(标签, 文本)]，缺失字段省略。"""
    units: list[tuple[str, str]] = []
    definition = clean(entry.get("definition", ""))
    if definition:
        units.append(("【释义】", definition))
    examples = entry.get("examples") or []
    ex_clean = [clean(e) for e in examples if clean(e)]
    if ex_clean:
        units.append(("【例句】", " ".join(ex_clean)))
    ground_truth = clean(entry.get("ground_truth", ""))
    if ground_truth:
        units.append(("【详解】", ground_truth))
    return units


def _render(head: str, part: list[tuple[str, str]], continued: bool) -> str:
    prefix = head + "（续）" if continued else head
    return prefix + "\n" + "\n".join(lb + tx for lb, tx in part)


def sentence_atoms(text: str) -> list[str]:
    """按句末标点把长文本切成原子句；超长单句再硬切。"""
    atoms: list[str] = []
    for sent in SENT_END.split(text):
        sent = sent.strip()
        while len(sent) > ATOM_MAX:
            atoms.append(sent[:ATOM_MAX])
            sent = sent[ATOM_MAX:].strip()
        if sent:
            atoms.append(sent)
    return atoms


def _merge_lines(atoms: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """同一字段的相邻原子句合并成一行，避免一行一句。"""
    lines: list[list[str]] = []
    for label, text in atoms:
        if lines and lines[-1][0] == label:
            lines[-1][1] += text
        else:
            lines.append([label, text])
    return [(label, text) for label, text in lines]


def make_chunks(term: str, units: list[tuple[str, str]]) -> list[str]:
    """把一个词条的字段拼成一个（或均衡拆分后多个）chunk 文本。"""
    body = "\n".join(label + text for label, text in units)
    head = f"【词条】{term}"
    total = len(head) + 1 + len(body)
    if total <= MAX_LEN:
        return [head + "\n" + body]

    # 超长：按句子切成原子，再均衡分到 ceil(total/MAX_LEN) 片
    atoms: list[tuple[str, str]] = []
    for label, text in units:
        for piece in sentence_atoms(text):
            atoms.append((label, piece))
    line_lens = [len(label) + len(text) + 1 for label, text in atoms]
    hard_cap = MAX_LEN - len(head) - 20
    # 用「原子行长度之和」估片长（含每片重复的词条头与字段标签），再均衡分片
    content = sum(line_lens) + len(head) + 1
    n_parts = max(2, -(-content // MAX_LEN))
    target = content / n_parts

    groups: list[list[tuple[str, str]]] = [[]]
    acc = 0
    for atom, line_len in zip(atoms, line_lens):
        if groups[-1] and (acc >= target or acc + line_len > hard_cap):
            groups.append([])
            acc = 0
        groups[-1].append(atom)
        acc += line_len

    # 收尾：末片过短则并入前一片，避免出现几十字的碎片
    if len(groups) > 1:
        last_len = sum(len(lb) + len(tx) + 1 for lb, tx in groups[-1])
        prev_len = sum(len(lb) + len(tx) + 1 for lb, tx in groups[-2])
        if last_len < target * 0.4 and prev_len + last_len <= hard_cap:
            groups[-2].extend(groups.pop())

    out: list[str] = []
    prev_label = ""
    for idx, group in enumerate(groups):
        lines = _merge_lines(group)
        rendered: list[tuple[str, str]] = []
        for pos, (label, text) in enumerate(lines):
            shown = label + "（续）" if (pos == 0 and label == prev_label) else label
            rendered.append((shown, text))
        block = _render(head, rendered, idx > 0)
        if len(block) > MAX_LEN:  # 兜底：对半拆（不重复字段标签）
            mid = max(1, len(rendered) // 2)
            out.append(_render(head, rendered[:mid], idx > 0))
            out.append(_render(head, rendered[mid:], True))
        else:
            out.append(block)
        prev_label = lines[-1][0]
    return out


def fetch_raw() -> str:
    print(f"[dl] {DATA_URL}")
    resp = requests.get(DATA_URL, proxies=PROXIES, timeout=180)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    print(f"[dl] {len(resp.content)} bytes")
    return resp.text


def parse_raw(text: str) -> dict:
    idx = text.index("rawdata")
    brace = text.index("{", idx)
    data = ast.literal_eval(text[brace:])
    if not isinstance(data, dict):
        raise SystemExit("parsed rawdata is not a dict")
    return data


def main() -> int:
    raw_text = fetch_raw()
    data = parse_raw(raw_text)
    print(f"[parse] {len(data)} entries")

    chunks: list[dict] = []
    seen: set[str] = set()
    split_terms: list[str] = []
    skipped_terms: list[str] = []

    for term, entry in data.items():
        name = clean(str(term))
        if not name or not isinstance(entry, dict):
            skipped_terms.append(str(term))
            continue
        units = build_units(entry)
        if not units:
            skipped_terms.append(name)
            continue
        term_chunks = make_chunks(name, units)
        for text in term_chunks:
            text = text.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            chunks.append({"id": len(chunks) + 1, "text": text})
        if len(term_chunks) > 1:
            split_terms.append(name)

    out_chunks = OUT_DIR / "chunks.jsonl"
    with out_chunks.open("w", encoding="utf-8", newline="\n") as fh:
        for item in chunks:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    lens = [len(c["text"]) for c in chunks]
    now = datetime.now(CST).isoformat(timespec="seconds")
    manifest = {
        "kb_name": "网络流行语释义库",
        "description": "中文网络流行语词条释义库：每条含【词条】【释义】【例句】【详解】，覆盖 B 站/微博/抖音等平台的高频热词与梗。",
        "emoji": "🗣️",
        "source_url": "https://github.com/SCUNLP/Buzzword",
        "source_license": (
            "上游仓库 SCUNLP/Buzzword 未提供 LICENSE 文件（GitHub API license 字段为空）；"
            "该数据为 ACL 2025 论文《Can Large Language Models Understand Internet Buzzwords "
            "Through User-Generated Content》（arXiv:2505.15071）的配套研究数据集，"
            "未声明开放许可。按研究／自用用途处理，对外再分发或商用前请先咨询原作者并引用论文。"
        ),
        "language": "zh-CN",
        "num_chunks": len(chunks),
        "built_at": now,
        "builder": "corpus-cheer",
        "notes": (
            f"数据文件 data.py（{len(data)} 个词条，下载时 5,214,058 字节）全量使用，未抽样。"
            "仅取上游 definition（释义）、examples（例句）、ground_truth（详解）三个字段；"
            "不使用 *_KEY（6 个模型生成的释义，含明显事实错误）与 *_score（模型互评）。"
            "仅 49 个词条带例句，其余条目省略【例句】行。"
            f"清洗：去零宽/控制字符、压缩空白、把上游用裸尖括号写的书名（如 <长河浪花集>）规范为《长河浪花集》，避免被误判为 HTML；"
            f"超长词条（>{MAX_LEN} 字符）按句末标点拆成多片，片首重复【词条】X（续），共 {len(split_terms)} 个词条被拆分。"
            "局限：释义为上游研究数据集标注/整理文本，个别条目可能有时效性偏差；"
            "同义词条（如“粉切黑/粉红切开都是黑”）各自成条，未合并；"
            "上游未提供 LICENSE，许可情况见 source_license。"
        ),
    }
    with (OUT_DIR / "manifest.json").open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"[out] {out_chunks}  chunks={len(chunks)}")
    print(f"[stat] len min={min(lens)} avg={sum(lens)//len(lens)} max={max(lens)}")
    print(f"[stat] split terms={len(split_terms)} skipped={len(skipped_terms)}")
    if split_terms:
        print(f"[stat] split sample={split_terms[:10]}")
    if skipped_terms:
        print(f"[stat] skipped={skipped_terms[:10]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
