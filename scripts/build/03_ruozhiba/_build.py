# NOTE: 本脚本为公开仓库导出时调整过的构建期参考实现，语料目录已改为仓库相对路径
#       （03_ruozhiba/）；运行前请先把原始数据放到 corpora/03_ruozhiba/raw/。
# -*- coding: utf-8 -*-
"""构建「弱智吧语料库」(03_ruozhiba)。

数据源（按任务给定优先级，实际可用的前两个都用了）：
  1) HF kirp/ruozhiba-raw -> wisdomBar_raw.csv（贴吧弱智吧原帖 92509 条，仅有标题/正文，无回答）
  2) HF LooksJuicy/ruozhiba -> ruozhiba_qa.json（1496 组「无厘头提问 + 一本正经解释」QA）
  3) ModelScope AI-ModelScope/ruozhiba：探测 404，不可用

构建:
  - 标题组 chunk：清洗后的原帖标题按主题分桶，5 条一组合并为「弱智吧神提问」chunk
  - 问答 chunk：QA 对按主题分桶，3–6 组一组合并为「弱智吧问答」chunk
"""
from __future__ import annotations

import os

import csv
import html
import json
import random
import re
from collections import Counter, OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / "corpora" / "03_ruozhiba"
RAW = HERE / "raw"

URL = re.compile(r"(https?://|www\.|tieba\.baidu\.com|pan\.baidu\.com)")
CONTACT = re.compile(
    r"(加微|加V|加v|微信|vx|VX|威信|QQ群|qq群|Q群|代购|刷单|兼职|日结|优惠券|公众号|"
    r"扫码|私信|广告|微商|引流|出售|回收|招代理|贷款|博彩|赌场)"
)
META = re.compile(
    r"(吧主|吧务|小吧|签到|水贴|水经验|申精|置顶|删帖|封禁|举报|吧规|经验\+|经验加|"
    r"升级|等级|关注本吧|新人报到|路过|前排|沙发|直播贴)"
)
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\u200b-\u200f\ufeff]")
HTML_TAG = re.compile(r"<[^>]{1,60}>")
SPACE = re.compile(r"\s+")

# ---------------------------------------------------------------- 主题
THEMES = OrderedDict([
    ("科学物理", ["物理", "化学", "地球", "宇宙", "引力", "光速", "原子", "相对论", "量子", "重力",
                "空气", "温度", "热能", "燃烧", "氧气", "二氧化碳", "磁场", "电流", "密度",
                "质量", "速度", "太空", "空间站", "太阳", "月亮", "星球", "黑洞", "时区", "纬度",
                "冰", "水蒸气", "浮力", "摩擦"]),
    ("生物医学", ["医生", "医院", "病人", "护士", "手术", "献血", "输血", "心脏", "大脑", "细胞",
                "DNA", "基因", "病毒", "细菌", "癌症", "吃药", "尸体", "怀孕", "生育", "器官",
                "解剖", "精神病", "院长", "中医", "疫苗", "体温", "麻醉", "艾滋"]),
    ("数学逻辑", ["数学", "数字", "概率", "方程", "公式", "面积", "体积", "函数", "等于", "除以",
                "乘以", "圆周率", "勾股", "数列", "统计", "逻辑", "集合", "平行", "证明", "小数点",
                "二进制", "奇数", "偶数"]),
    ("历史社会", ["秦始皇", "皇帝", "历史", "朝代", "战争", "将军", "革命", "总统", "国家",
                "警察", "法院", "判刑", "法律", "犯罪", "监狱", "抗日", "三国", "唐僧", "孙悟空",
                "孔乙己", "杜甫", "李白", "鲁迅", "和珅", "太监", "衙门", "皇帝", "大臣", "圣旨",
                "考古", "文物"]),
    ("动物植物", ["动物", "猫", "狗", "猪", "牛", "鸡", "鸭", "鱼", "蚊子", "蚂蚁", "鸟", "蛆",
                "苍蝇", "蟑螂", "大象", "老鼠", "熊猫", "兔子", "植物", "树", "花", "草", "蘑菇",
                "蚯蚓", "乌龟", "青蛙", "麻雀", "羊", "马", "驴"]),
    ("日常起居", ["吃饭", "睡觉", "洗澡", "上厕所", "刷牙", "衣服", "上班", "学校", "公交",
                "手机", "空调", "冰箱", "外卖", "杯子", "袜子", "床", "被子", "理发", "电梯",
                "马桶", "牙膏", "拖鞋", "钥匙", "钱包", "枕头", "窗帘"]),
    ("情感家庭", ["女朋友", "男朋友", "女友", "男友", "老婆", "老公", "父母", "妈妈", "爸爸",
                "孩子", "儿子", "女儿", "结婚", "恋爱", "分手", "相亲", "亲戚", "兄弟", "闺蜜",
                "离婚", "婚礼", "初恋", "婆婆", "岳父", "丈母娘"]),
    ("语言文字", ["字", "词", "话", "名字", "拼音", "意思", "翻译", "字母", "汉字", "方言",
                "谐音", "成语", "歇后语", "标点", "造句", "缩写", "英文", "语文", "读音",
                "多音字", "同音", "反义词"]),
    ("宗教哲学", ["上帝", "佛", "神仙", "鬼", "灵魂", "天堂", "地狱", "转世", "人生", "哲学",
                "命运", "轮回", "菩萨", "耶稣", "天使", "魔鬼", "许愿", "寺庙", "道士", "阎王",
                "孟婆", "投胎", "算命", "星座"]),
    ("工作职场", ["老板", "员工", "加班", "工资", "工作", "公司", "面试", "简历", "同事", "厂长",
                "领导", "打工人", "实习", "职场", "客户", "甲方", "年终奖", "裁员", "上班族"]),
    ("网络科技", ["网友", "贴吧", "吧友", "网络", "微博", "微博", "电脑", "游戏", "WiFi", "直播",
                "程序员", "AI", "人工智能", "算法", "机器人", "黑客", "无人机", "浏览器", "内存",
                "键盘", "屏幕", "软件", "充电", "信号"]),
    ("经济消费", ["钱", "银行", "价格", "买", "卖", "工资", "彩票", "股票", "房价", "贷款",
                "理财", "消费", "超市", "奶茶", "红包", "转账", "支付宝", "存款", "利息",
                "打折", "优惠", "付款"]),
])


def theme_of(text: str) -> str:
    best, best_score = "杂谈", 0
    for theme, kws in THEMES.items():
        score = sum(1 for kw in kws if kw in text)
        if score > best_score:
            best, best_score = theme, score
    return best


# ---------------------------------------------------------------- 标题
def clean_title(s: str) -> str:
    s = html.unescape(s or "")
    s = HTML_TAG.sub("", s)
    s = CTRL.sub("", s)
    s = s.replace("\r", " ").replace("\n", " ")
    s = SPACE.sub(" ", s).strip()
    s = s.strip(" ,，。.、;；:：!！~～-—")
    s = re.sub(r"\s*(?:rt|RT|如题)\s*$", "", s).strip()
    return s


def load_titles():
    path = RAW / "kirp__ruozhiba-raw__wisdomBar_raw.csv"
    rows = list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    out, seen = [], set()
    cjk = re.compile(r"[\u4e00-\u9fff]")
    for r in rows:
        t = clean_title(r.get("title", ""))
        n = len(t)
        if not t or n < 8 or n > 60:
            continue
        if URL.search(t) or CONTACT.search(t) or META.search(t):
            continue
        if re.fullmatch(r"[\W_]+", t) or len(set(t)) <= 2:
            continue
        # 火星文/拼音/乱码占比过高
        if len(cjk.findall(t)) / n < 0.5:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return rows, out


# ---------------------------------------------------------------- QA
def load_qa():
    path = RAW / "LooksJuicy__ruozhiba__ruozhiba_qa.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    out, seen = [], set()
    for item in data:
        q = clean_title(item.get("instruction", ""))
        a = clean_title(item.get("output", ""))
        if not q or not a:
            continue
        if len(q) < 4 or len(q) > 120 or len(a) > 180:
            continue
        if URL.search(q) or URL.search(a) or CONTACT.search(q) or CONTACT.search(a):
            continue
        key = (q, a)
        if key in seen:
            continue
        seen.add(key)
        out.append((q, a))
    return data, out


# ---------------------------------------------------------------- 组块
def _balanced_sizes(n: int, target: int = 5, lo: int = 3, hi: int = 6):
    """把 n 条切成大小在 [lo, hi] 的若干组（尽量接近 target）。"""
    if n <= 0:
        return []
    k = max(1, -(-n // hi), round(n / target))
    if n < lo:
        return [n]
    while True:
        base, rem = divmod(n, k)
        if base <= hi and (base >= lo or n < lo):
            sizes = [base + 1] * rem + [base] * (k - rem)
            return sizes
        k += 1
        if k > n:
            return [n]


def balanced_pack(units, target=5, lo=3, hi=6):
    sizes = _balanced_sizes(len(units), target, lo, hi)
    out, i = [], 0
    for s in sizes:
        out.append(units[i:i + s])
        i += s
    return out


def pack(units, per_chunk):
    """QA 组块：每块 3–6 组，超长时在问答边界拆开（单块控制在 1150 字符内）。"""
    groups = [units[i:i + per_chunk] for i in range(0, len(units), per_chunk)]
    if len(groups) >= 2 and len(groups[-1]) < 3:
        tail = groups.pop()
        if len(groups[-1]) + len(tail) <= 6:
            groups[-1] = groups[-1] + tail
        else:
            groups.append(tail)
    final = []
    for g in groups:
        cur, cur_len = [], 30
        for u, w in g:
            if cur and cur_len + w > 1150:
                final.append(cur)
                cur, cur_len = [], 30
            cur.append(u)
            cur_len += w
        if cur:
            final.append(cur)
    return final


def render_titles(theme: str, titles) -> str:
    head = f"弱智吧神提问（{theme}）：\n" if theme != "杂谈" else "弱智吧神提问（杂谈）：\n"
    body = "\n".join(f"{i}. {t}" for i, t in enumerate(titles, start=1))
    return head + body


# 弱智吧反复出现的固定角色 / 社会新闻体标签：同角色同话题的段子放在一个 chunk 里
ENTITIES = [
    "王老汉", "小明", "王警官", "食人族", "小红", "老王", "院长", "张医生", "李医生",
    "王先生", "李老汉", "小张", "小王", "王女士", "小明妈", "小明爸", "老李", "小陈",
    "男子", "女子", "大爷", "大妈", "老汉", "记者", "据报道", "专家", "网友",
    "老师", "学生", "同学", "朋友", "厕所", "飞机", "宝马", "老鼠",
]


def entity_of(title: str):
    for e in ENTITIES:
        if e in title:
            return e
    return None


def render_qa(qas) -> str:
    parts = [f"问：{q}\n答：{a}" for q, a in qas]
    return "弱智吧问答（一本正经地解释无厘头提问）：\n" + "\n\n".join(parts)


def main():
    rows, titles = load_titles()
    qa_raw, qas = load_qa()
    print(f"帖子原始 {len(rows)}，可用标题 {len(titles)}；QA 原始 {len(qa_raw)}，可用 {len(qas)}")

    # ---- 标题抽样：固定种子随机抽样（全量 8.8 万条 -> 抽样 4800 条）
    SAMPLE_TITLES = 4800
    rng = random.Random(20261026)
    picked = rng.sample(titles, SAMPLE_TITLES)
    buckets = OrderedDict((t, []) for t in THEMES)
    buckets["杂谈"] = []
    for t in picked:
        buckets[theme_of(t)].append(t)
    title_chunks = []
    for theme in list(THEMES.keys()):
        for g in balanced_pack(buckets[theme]):
            title_chunks.append(render_titles(theme, g))
    # 「杂谈」再按固定角色/社会新闻体细分，提升 chunk 内语境一致性；
    # 角色条数不足 5 的并入杂谈总池，避免出现 1–2 条的碎 chunk
    ent_buckets = OrderedDict((e, []) for e in ENTITIES)
    ent_counts = Counter()
    ent_of_item = []
    for item in buckets["杂谈"]:
        ent = entity_of(item)
        ent_of_item.append(ent)
        if ent:
            ent_counts[ent] += 1
    leftover = []
    for item, ent in zip(buckets["杂谈"], ent_of_item):
        if ent and ent_counts[ent] >= 5:
            ent_buckets[ent].append(item)
        else:
            leftover.append(item)
    for ent, items in ent_buckets.items():
        if not items:
            continue
        for g in balanced_pack(items):
            title_chunks.append(render_titles(f"杂谈·{ent}系列", g))
    for g in balanced_pack(leftover):
        title_chunks.append(render_titles("杂谈", g))
    print("标题 chunk:", len(title_chunks), "主题分布:", Counter(theme_of(t) for t in picked))

    # ---- QA：主题分桶，4 组/条
    qa_buckets = OrderedDict((t, []) for t in THEMES)
    qa_buckets["杂谈"] = []
    for q, a in qas:
        qa_buckets[theme_of(q + a)].append(((q, a), len(q) + len(a) + 8))
    qa_chunks = []
    for theme in ["杂谈"] + list(THEMES.keys()):
        groups = pack(qa_buckets[theme], 4)
        for g in groups:
            qa_chunks.append(render_qa(g))
    print("QA chunk:", len(qa_chunks))

    chunks = title_chunks + qa_chunks
    # 兜底去重/长度
    seen, out = set(), []
    for c in chunks:
        if c in seen:
            continue
        if len(c) < 60 or len(c) > 1200:
            continue
        seen.add(c)
        out.append(c)
    print("总计:", len(out))
    lens = [len(c) for c in out]
    print(f"长度 min={min(lens)} avg={sum(lens)//len(lens)} max={max(lens)}")

    with (HERE / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for i, text in enumerate(out):
            fh.write(json.dumps({"id": i, "text": text}, ensure_ascii=False) + "\n")

    tz = timezone(timedelta(hours=8))
    manifest = {
        "kb_name": "弱智吧语料库",
        "description": "百度贴吧「弱智吧」风格的语料：无厘头神提问 + 一本正经的歪解，学会用反逻辑的方式抖机灵。",
        "emoji": "🧠",
        "source_url": "https://huggingface.co/datasets/kirp/ruozhiba-raw ; https://huggingface.co/datasets/LooksJuicy/ruozhiba",
        "source_license": "贴吧用户原创内容（公开抓取数据集）/ 仅限自用；避免商用与原文转载",
        "language": "zh-CN",
        "num_chunks": len(out),
        "built_at": datetime.now(tz).isoformat(timespec="seconds"),
        "builder": "corpus-meme-bar",
        "notes": (
            "数据源：① HF kirp/ruozhiba-raw 的 wisdomBar_raw.csv（弱智吧原帖 92509 条，仅标题无回答）；"
            "② HF LooksJuicy/ruozhiba 的 ruozhiba_qa.json（1496 组无厘头提问+一本正经解释）；"
            "③ ModelScope AI-ModelScope/ruozhiba 探测 404 不可用。"
            f"标题清洗后可用 {len(titles)} 条，固定种子随机抽样 {len(picked)} 条（seed=20261026），"
            f"按 12 个主题分桶后每 4–6 条合并，生成 {len(title_chunks)} 条「弱智吧神提问」chunk；"
            "「杂谈」桶再按王老汉/小明/食人族/社会新闻体等固定角色细分。"
            f"QA 清洗后 {len(qas)} 组，按主题每 3–6 组合并，生成 {len(qa_chunks)} 条「弱智吧问答」chunk。"
            "清洗：去 HTML/URL/联系方式/广告/吧务签到等元帖、过短(<8字)过长(>60字)标题、"
            "非中文占比过高(火星文/乱码)、过长解释性答案(>180字)、完全重复项；不改写原文。"
            "已知局限：原帖标题是正文，多数没有回答，标题组 chunk 只呈现提问风格；"
            "QA 子集来自另一数据源，答案为「认真解释无厘头问题」的冷面幽默，与原帖标题语气略有差异。"
        ),
    }
    (HERE / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("manifest written")


if __name__ == "__main__":
    main()
