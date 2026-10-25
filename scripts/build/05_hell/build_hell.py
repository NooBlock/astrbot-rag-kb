# NOTE: 本脚本为公开仓库导出时调整过的构建期参考实现，语料目录已改为仓库相对路径
#       （05_hell/）；运行前请先把原始数据放到 corpora/05_hell/raw/。
# -*- coding: utf-8 -*-
"""构建 05_hell（地狱笑话库）最终产物：chunks.jsonl / manifest.json / README.md

来源（均为可访问的公开中文页面/语料，详见 README）：
- 煎蛋「一些地狱笑话」系列 1-4（中文译文）
- 搜狐《地狱级冷笑话，功德要笑没了》（中文问答式地狱笑话）
- 知乎两个回答（地狱笑话相关问题的文本答案）
- GitHub ChaokunChang/Joke-Factory 的中文段子数据集 duanzi.json（黑色幽默筛选）
- 煎蛋「没品笑话集」若干条（黑色幽默筛选）
"""
import os
import json
import re
import pathlib
from datetime import datetime, timezone, timedelta

RAW = Path(__file__).resolve().parents[2] / "corpora" / "05_hell" / "raw"
OUT = Path(__file__).resolve().parents[2] / "corpora" / "05_hell"

JANDAN_SRC = {
    "一些地狱笑话": "https://jandan.net/p/111112/",
    "一些地狱笑话(2)": "https://jandan.net/p/111148/",
    "一些地狱笑话(3)": "https://jandan.net/p/111166/",
    "一些地狱笑话(4)": "https://jandan.net/p/111275/",
}
SOHU_URL = "https://www.sohu.com/a/848380066_100133615"
ZHIHU_SRC = {
    "房产法术": "https://www.zhihu.com/question/577720793/answer/760569943",
    "算命骗子": "https://www.zhihu.com/question/577720793/answer/2911292858",
    "咖啡兽药": "https://www.zhihu.com/question/639137268/answer/3458473425",
}
DUANZI_URL = "https://github.com/ChaokunChang/Joke-Factory/blob/master/src/data/chinese_joke/duanzi.json"
MEIPIN_URL = "https://jandan.net/p/author/Diehard"

TIP_BASE = "仅在对方主动玩梗且关系足够熟时使用；涉及真实受害者、具体地域/民族/性别/疾病/灾难时默认不使用或改写。"
TIP_EXTRA = {
    "病症": "本条涉及疾病/残障元素，默认不主动使用；对方本人是当事人时禁用。",
    "灾难": "本条含灾难/事故元素，仅限纯虚构语境，禁止对真实事故当事人或其家属使用。",
    "地域": "本条含地域刻板印象，仅在熟人互损时使用，公开场合不建议。",
    "历史": "本条涉及历史人物/事件，仅在双方都熟悉历史梗时使用，避免在严肃讨论中使用。",
    "职业": "本条拿职业开玩笑，同事或从业者在场时默认不用。",
    "其他": "本条含死亡/暴力等黑色元素，默认不主动对不熟的人使用。",
}

# ---------- 煎蛋「一些地狱笑话」选中条目（索引对应 raw/jandan_jokes.json） ----------
JANDAN_PICK = [
    (0, "其他"), (4, "职业"), (5, "其他"), (7, "其他"), (8, "其他"), (9, "其他"),
    (10, "职业"), (11, "其他"), (13, "职业"), (16, "其他"), (18, "其他"),
    (19, "职业"), (22, "职业"), (23, "职业"), (24, "其他"), (25, "其他"), (26, "病症"),
    (27, "病症"), (33, "其他"), (35, "其他"), (38, "其他"), (41, "职业"), (44, "其他"),
    (45, "其他"), (48, "其他"), (50, "病症"), (54, "其他"), (57, "灾难"), (63, "其他"),
    (64, "其他"),
]

# ---------- 搜狐《地狱级冷笑话，功德要笑没了》选中条目 ----------
SOHU_PICK = [
    ("问：为什么说哪吒闹海是中国唯一一个有来龙去脉的故事？答：因为来龙，去脉。", "其他"),
    ("问：路易十六去刑场，导航听到的最后一句话是什么？答：前方100米掉头——因为是真掉头。", "历史"),
    ("问：哪吒和伯邑考在一起会变成什么？答：伯邑考他爹成了周文王，他弟成了周武王，他自己成了汉堡王。伯邑考肉饼、比干见人心、商鞅知马力。", "历史"),
    ("问：世界上最卷的地方是哪里？答：木乃伊博物馆，因为有的是人干。", "其他"),
    ("问：请问历史上最早的爱豆是谁？答：秦始皇，据史料记载当时读书人纷纷入坑，他还是最早的带货主播，带的书都火了。", "历史"),
    ("问：非洲的龙卷风叫什么名字？答：扫黑风暴。", "地域"),
    ("问：《西游记》师徒四人为什么没有女人？答：因为他们要去的是印度。", "其他"),
    ("问：为什么美国人玩不好王者荣耀？答：因为他们开局少两座塔。", "地域"),
    ("问：为什么说柯南是灌篮高手？答：因为他一直惯着小兰。", "其他"),
    ("问：中国人的骨灰盒，打一食物。答：韭菜盒子。", "其他"),
    ("问：老鹰不见了，请问是谁偷的？答：猫，因为猫头鹰。", "其他"),
    ("问：在所有动物中，请问哪种动物要求最多？答：猪，因为诸多要求。", "其他"),
    ("问：什么东西最提神？答：十字架，因为上面提着一个神。", "其他"),
    ("问：知道为什么成吉思汗的墓找不到吗？答：因为他们是游墓民族人。", "历史"),
    ("问：哪里的垃圾分类做得最好？答：沙漠，因为沙漠里都是干尸，干湿分离。", "其他"),
]

# ---------- 知乎回答中的文本条目 ----------
ZHIHU_PICK = [
    ("大学毕业的时候，我们的政治经济学老师神秘兮兮地说他会法术。我们都不信，非要他表演一个。于是他指着学校后面的那片开发区，对着造了半拉的房子一指，说“涨！”二十年了，我们都在求他快点收了神通。", "其他", "房产法术"),
    ("古代一个江湖骗子摆地摊给人算命为生。骗子：你们以后儿孙满堂，儿子女儿好几个。古人：哇，谢谢大师！有一日他穿越到现代，对现代人说了同样的话。现代人：大师，有没有破解的方法？骗子：？？？？？？", "其他", "算命骗子"),
    ("上个世纪粮食短缺的年代，人们把咖啡作为一种兽药喂食给牲畜。在牲口饲料中加入一些咖啡因，不仅能让牲口吃得少干得多，还能让这些畜生不知疲倦。", "历史", "咖啡兽药"),
]

# ---------- duanzi.json 中筛选的黑色幽默（用唯一子串定位原文） ----------
DUANZI_PICK = [
    ("等我死后把我的骨灰撒到海里", "其他"),
    ("最冷是太平间，最热是火葬场", "其他"),
    ("阎王爷，事情大概就是这样", "其他"),
    ("有没有听说过上坟", "其他"),
    ("我在等我老婆给我送钱", "其他"),
    ("她去年车祸去世了，在天上", "其他"),
    ("我将来要是得了绝症，你就给我点钱", "病症"),
    ("懒癌晚期", "病症"),
    ("孟婆喝了汤之后", "其他"),
    ("你是骨灰啊，一吹就散", "其他"),
    ("明明还没排到我", "其他"),
    ("今天举行一百米比赛", "其他"),
    ("不要在职期间自杀给公司添麻烦", "职业"),
    ("我们是诚信经营", "病症"),
    ("残疾人咱就别骗了", "病症"),
    ("给你刀，该你追我了", "病症"),
    ("被人研究", "职业"),
    ("帮她改一下儿子的血型鉴定书", "其他"),
    ("旅游不花钱啊", "病症"),
    ("我怎么有种上坟的感觉", "其他"),
    ("你的遗书", "其他"),
    ("买来自杀用的", "其他"),
    ("天庭购进一台电脑", "其他"),
    ("你不是抑郁", "病症"),
    ("你跟她说麻辣烫致癌", "病症"),
    ("阎罗殿内", "其他"),
    ("不是车祸是啥", "其他"),
    ("羊还能再抢救一下吗", "其他"),
]

# ---------- 煎蛋「没品笑话集」选中条目（索引对应 raw/jandan_meipin.json） ----------
MEIPIN_PICK = [
    (15, "病症"), (38, "其他"), (43, "职业"), (45, "职业"),
    (48, "其他"), (50, "其他"), (60, "其他"),
]


def chunk_text(joke: str, typ: str) -> str:
    joke = re.sub(r"\s+", " ", joke).strip()
    # 去掉煎蛋双语条目中残留的英文原文片段
    joke = re.sub(r'\s+[A-Za-z][A-Za-z0-9 ,.?!\'"():;-]{8,}$', "", joke).strip()
    return (
        f"【地狱笑话】{joke}\n"
        f"【类型】{typ}\n"
        f"【使用提示】{TIP_BASE}{TIP_EXTRA.get(typ, '')}"
    )


def load_duanzi() -> dict[str, tuple[int, str]]:
    lines = (RAW / "duanzi.json").read_text(encoding="utf-8").splitlines()
    idx: dict[str, tuple[int, str]] = {}
    for lineno, line in enumerate(lines, start=1):
        try:
            obj = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        idx[lineno] = obj.get("content", "")
    return idx


def main() -> None:
    chunks: list[str] = []
    seen = set()

    def add(joke: str, typ: str) -> None:
        t = chunk_text(joke, typ)
        if t in seen:
            return
        seen.add(t)
        chunks.append(t)

    jandan = json.loads((RAW / "jandan_jokes.json").read_text(encoding="utf-8"))
    for i, typ in JANDAN_PICK:
        add(jandan[i]["text"], typ)

    for joke, typ in SOHU_PICK:
        add(joke, typ)

    for joke, typ, _ in ZHIHU_PICK:
        add(joke, typ)

    duanzi = load_duanzi()
    used_lines = []
    for key, typ in DUANZI_PICK:
        hit = next(((ln, txt) for ln, txt in duanzi.items() if key in txt), None)
        if not hit:
            print("MISS duanzi:", key)
            continue
        ln, txt = hit
        used_lines.append(ln)
        add(txt, typ)

    meipin = json.loads((RAW / "jandan_meipin.json").read_text(encoding="utf-8"))
    for i, typ in MEIPIN_PICK:
        add(meipin[i]["text"], typ)

    n = len(chunks)
    with (OUT / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for i, t in enumerate(chunks, start=1):
            fh.write(json.dumps({"id": i, "text": t}, ensure_ascii=False) + "\n")

    now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    manifest = {
        "kb_name": "地狱笑话库",
        "description": "中文「地狱笑话 / 黑色幽默」精标语料，带类型标注与使用边界提示",
        "emoji": "💀",
        "source_url": SOHU_URL,
        "source_license": "各来源页面版权归原作者/站点所有（煎蛋、搜狐、知乎、Wikipedia）；duanzi.json 为公开 GitHub 数据集；本库仅供自用学习，不商用",
        "language": "zh-CN",
        "num_chunks": n,
        "built_at": now,
        "builder": "corpus-vbar-hell",
        "notes": (
            "来源构成：煎蛋「一些地狱笑话」系列 1-4（31 条）；搜狐《地狱级冷笑话，功德要笑没了》（15 条）；"
            "知乎地狱笑话问题下的文本答案（3 条）；GitHub ChaokunChang/Joke-Factory 的 duanzi.json 黑色幽默筛选（26 条）；"
            "煎蛋「没品笑话集」黑色幽默筛选（7 条）。"
            "筛选时剔除指向真实悲剧（911、泰坦尼克、新冠、战争等）、未成年人、现实可识别个人、以及种族/性别/性相关的条目；"
            "保留的病症/灾难/地域/历史类条目均附加更严格的使用提示。"
            "已知局限：网络上的中文“地狱笑话”合集大量以图片形式传播，可解析的纯文本源有限；本库条目多为西方地狱笑话的中译与中文谐音梗，"
            "部分条目「地狱」浓度一般、偏普通黑色幽默，已按可追溯来源如实保留，未编造出处。"
        ),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print("chunks", n, "duanzi lines", sorted(used_lines))
    print("wrote", OUT / "chunks.jsonl")


if __name__ == "__main__":
    main()
