# NOTE: 本脚本为公开仓库导出时调整过的构建期参考实现，语料目录已改为仓库相对路径
#       （04_vbar/）；运行前请先把原始数据放到 corpora/04_vbar/raw/。
# -*- coding: utf-8 -*-
"""构建 04_vbar（V吧黑话库）最终产物：chunks.jsonl / manifest.json / README.md

来源：
1. 知乎《v吧常见黑话大全》（节选）——XMMATRIX 回答
   https://www.zhihu.com/question/434737537/answer/1641781496
2. 萌娘百科《虚拟UP主用语与梗》
   https://zh.moegirl.org.cn/虚拟UP主用语与梗
"""
import os
import json
import re
import pathlib
from datetime import datetime, timezone, timedelta

RAW = Path(__file__).resolve().parents[2] / "corpora" / "04_vbar" / "raw"
OUT = Path(__file__).resolve().parents[2] / "corpora" / "04_vbar"

ZHIHU_URL = "https://www.zhihu.com/question/434737537/answer/1641781496"
MOE_URL = "https://zh.moegirl.org.cn/%E8%99%9A%E6%8B%9FUP%E4%B8%BB%E7%94%A8%E8%AF%AD%E4%B8%8E%E6%A2%97"

# 能写出具体圈内例句的词条（其余词条不生成模板句）
EXAMPLES = {
    "毕业": "例：主播发公告说「要毕业了」，是指她将引退、停止虚拟UP主活动。",
    "出道": "例：新人VUP发布自我介绍视频，弹幕会刷「恭喜出道」。",
    "冲塔": "例：有人在直播弹幕里追问主播中之人是谁，这就是「冲塔」，通常会被劝阻。",
    "DD": "例：同时关注十几个虚拟主播的观众会自嘲「我是DD」。",
    "单推": "例：只给一位VUP上舰、打SC的粉丝会说「我只单推她」。",
    "箱推": "例：喜欢整个hololive或彩虹社的观众会自称「箱推」。",
    "棉花糖": "例：主播说「来念棉花糖」，就是念观众匿名投稿的提问。",
    "切片": "例：把直播里好笑的片段剪成一分钟短视频发出来，弹幕会说「这个切片笑死」。",
    "转播man": "例：主播只在YouTube开播时，B站观众靠「转播man」同步看。",
    "中之人": "例：讨论皮套背后真人是谁，就是在聊这位VUP的「中之人」。",
    "皮套": "例：主播换了新模型，弹幕会刷「换皮套了」。",
    "套皮": "例：不认真做VUP、只借虚拟形象直播的主播，会被说是「套皮主播」。",
    "SC": "例：观众花钱发醒目留言，弹幕会跟着刷「感谢SC」。",
    "同接数": "例：两家粉丝比拼「同接数」，就是比直播同时在线人数。",
    "贴贴": "例：两位主播联动互动很甜，粉丝会刷「贴贴」。",
    "炎上": "例：主播失言被全网批评，圈子会说「又炎上了」。",
    "清楚": "例：新人主播言行端庄乖巧，会被夸「好清楚」。",
    "整活": "例：主播在直播里搞怪整蛊，弹幕会说「又整活了」。",
    "转生": "例：VUP注销后换账号重新出道，圈内称为「转生」。",
    "前世": "例：查某位VUP以前的活动账号，就是查她的「前世」。",
    "awsl": "例：看到主播的可爱画面，弹幕会刷「awsl」。",
    "kksk": "例：直播里出现精彩片段，弹幕会刷「kksk」（ここすき）。",
    "hshs": "例：听到主播温柔的声音，弹幕会刷「hshs」。",
    "管人": "例：把虚拟主播统称为「管人」，如「管人金曲」「管人观众」。",
    "会限/会员限定": "例：只有频道会员能看的直播叫「会限」。",
    "突待/凸待": "例：主播临时连麦观众聊天，叫「凸待」。",
    "收益化": "例：频道开通打赏与会员功能，称为「收益化」。",
    "2D回/3D回": "例：用2D立绘直播叫「2D回」，用3D模型直播叫「3D回」。",
    "限定公开": "例：标注「限定公开」的视频，只有会员或特定对象能看。",
    "同传Man": "例：外语直播时靠「同传Man」在弹幕里实时翻译。",
    "云P": "例：没看直播就凭脑补批评主播的观众，会被说是「云P」。",
    "情强": "例：对主播的人际关系、内幕知道很多的观众，被称为「情强」。",
}

SKIP_MOE = {
    "x oo x", "○x○", "我们仨", "不要做得太过分，日本人", "拆腻子都是白毛控吗",
    "露易丝定型文", "睡过头了，真的非常抱歉", "你来啦，神回，删档，没录，不烤",
    "nico生主", "四天王", "食杀", "Yagoo", "PH-P", "repo", "龙", "杏", "虹", "妈妈",
}


def clean_md(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
        text = re.sub(r"\[\[[^\]]*\]\]\([^)]*\)", "", text)
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("~~", "")
    text = re.sub(r"「([^」]+)」", r"\1", text)
    text = re.sub(r"参见：[^。；]*[。；]?", "", text)
    # 清理 markdown 小标题与列表符号
    text = re.sub(r"#{1,6}\s*", "；", text)
    text = re.sub(r"(^|\s)\*\s+", r"\1", text)
    text = text.replace("*", "")
    text = re.sub(r"[；;]\s*(?=[；;])", "", text)
    text = re.sub(r"\s*；\s*", "；", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"；\s*$", "。", text)
    return text.strip("；。 ")


def parse_moegirl() -> list[dict]:
    t = (RAW / "moegirl_vup_terms.txt").read_text(encoding="utf-8")
    lines = t.splitlines()
    items = []
    for i, line in enumerate(lines):
        if not line.startswith("### "):
            continue
        name = clean_md(line[4:].strip())
        body = []
        j = i + 1
        while j < len(lines) and not lines[j].startswith(("## ", "### ")):
            raw = lines[j].strip()
            s = clean_md(raw).strip()
            if raw.startswith("#") and s:
                s = "；" + s
            if s and not s.startswith("主条目") and not s.startswith("主段落"):
                body.append(s)
            j += 1
        desc = " ".join(b for b in body if b).strip()
        if not name or len(desc) < 20:
            continue
        items.append({"name": name, "desc": desc})
    return items


def parse_zhihu() -> list[dict]:
    cand = list(RAW.glob("zhihu_answer_*.txt")) + list(RAW.glob("zhihu_try_*.txt"))
    text = ""
    for p in cand:
        s = p.read_text(encoding="utf-8")
        if "v吧常见黑话大全" in s:
            text = s
            break
    if not text:
        raise SystemExit("未找到知乎回答文本")
    start = text.index("《v吧常见黑话大全》（节选）")
    end = text.index("……………………", start)
    block = text[start:end]
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    cur = None
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("《v吧常见黑话大全"):
            continue
        if line.startswith("/*"):
            line = line[2:].strip()
        if line.startswith("*/"):
            continue
        if line.endswith("篇：") or line == "其他：":
            cur = line.rstrip("：")
            if cur not in sections:
                sections[cur] = []
                order.append(cur)
            continue
        if cur and "：" in line:
            # 跳过注释性说明行（以“鉴于”“现在吧友”等开头，无冒号键名）
            sections[cur].append(line)
    out = []
    for sec in order:
        for line in sections[sec]:
            if "：" not in line:
                continue
            key, val = line.split("：", 1)
            key = key.strip()
            val = val.strip()
            if not key or key == "\\" or not val:
                continue
            out.append({"section": sec, "name": key, "desc": val})
    return out


def main() -> None:
    moe = parse_moegirl()
    zh = parse_zhihu()
    chunks: list[str] = []
    seen = set()

    def add(text: str) -> None:
        if text in seen:
            return
        seen.add(text)
        chunks.append(text)

    for it in moe:
        if it["name"] in SKIP_MOE:
            continue
        desc = re.sub(r"\s+", " ", it["desc"])
        desc = re.sub(r"\s*；\s*", "；", desc)
        if len(desc) > 400:
            desc = desc[:397] + "…"
        text = (
            f"【词条】{it['name']}\n"
            f"【释义】{desc}\n"
            f"【出处/语境】萌娘百科《虚拟UP主用语与梗》「{it['name']}」条（{MOE_URL}）"
        )
        ex = EXAMPLES.get(it["name"])
        if ex:
            text += f"\n【用法示例】{ex}"
        add(text)

    kind_phrase = {
        "v篇": "V吧对具体虚拟主播的阵营化称呼（多为黑称）",
        "组织篇": "V吧对运营公司、论坛等组织的代称",
        "群体篇": "V吧对粉丝群体、论坛用户的代称",
        "其他": "V吧常用黑话",
    }
    section_tip = {
        "v篇": "注意：此类称呼多为黑称，带阵营与贬义色彩，只在熟悉V吧语境的玩梗场合使用，粉丝向场合应避免。",
        "组织篇": "注意：此类代称带调侃/贬义色彩，正式场合不宜使用。",
        "群体篇": "注意：此类称呼多带贬义或自嘲色彩，跨圈使用容易引战。",
        "其他": "注意：属吧内黑话，圈外使用易造成误解。",
    }
    for it in zh:
        term = re.sub(r"\s*/\s*", " / ", it["name"])
        target = it["desc"].strip().rstrip("。")
        if "歧义项" in target:
            body = f"「{term}」是V吧用语，属歧义项，可指代七海nana7mi或七海美波，具体视上下文而定。"
        else:
            body = f"「{term}」是{kind_phrase.get(it['section'], 'V吧黑话')}，指{target}。{section_tip.get(it['section'], '')}"
        first = re.split(r"\s*/\s*", term)[0]
        text = (
            f"【词条】{term}\n"
            f"【释义】{body}\n"
            f"【出处/语境】知乎《v吧常见黑话大全》（节选），XMMATRIX（{ZHIHU_URL}）\n"
            f"【用法示例】例：在V吧帖子里看到「{first}」，通常就是指{target if '歧义项' not in target else '七海nana7mi 或 七海美波'}。"
        )
        add(text)

    n = len(chunks)
    now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    with (OUT / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for i, t in enumerate(chunks, start=1):
            fh.write(json.dumps({"id": i, "text": t}, ensure_ascii=False) + "\n")

    manifest = {
        "kb_name": "V吧黑话库",
        "description": "V吧 / V圈黑话与圈层用语精标库：词条释义、出处语境与用法示例",
        "emoji": "🎭",
        "source_url": ZHIHU_URL,
        "source_license": "知乎回答与萌娘百科内容版权归原作者/站点所有，萌娘百科内容不可商用；本库仅供自用学习",
        "language": "zh-CN",
        "num_chunks": n,
        "built_at": now,
        "builder": "corpus-vbar-hell",
        "notes": (
            "来源：①知乎《v吧常见黑话大全》（节选），XMMATRIX 回答；②萌娘百科《虚拟UP主用语与梗》。"
            "仅收录两处来源可追溯的词条，未收录无法验证的称谓语（如“舰长/提督”等B站大航海等级词，因缺少可引用释义页而暂缺）。"
            "每条含【词条】【释义】【出处/语境】；部分常见词条附【用法示例】（示例句为构建者按圈内语境撰写，非原文引用）。"
            "黑称类词条已加使用提醒，仅供理解语料，不建议在粉丝向场合使用。"
        ),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print("chunks", n)
    print("wrote", OUT / "chunks.jsonl")


if __name__ == "__main__":
    main()
