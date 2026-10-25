# NOTE: 本脚本为公开仓库导出时调整过的构建期参考实现，语料目录已改为仓库相对路径
#       （02_meme_style/）；运行前请先把原始数据放到 corpora/02_meme_style/raw/。
# -*- coding: utf-8 -*-
"""构建「网梗对话风格库」(02_meme_style)。

数据源: HuggingFace GaryYang123/zh-meme-sft-8k (train.jsonl 7377 + validation.jsonl 868)
策略:
  1. 解析 messages -> (user, assistant) 对
  2. 过滤: 空串/纯符号/广告联系方式/URL/过长通用AI式回答/重复
  3. 按关键词分主题桶, 同桶内每 4-6 组合并为 1 条 chunk (同 chunk 语境一致)
  4. 输出 chunks.jsonl / manifest.json / README.md
"""
from __future__ import annotations

import os

import json
import re
from collections import Counter, OrderedDict
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / "corpora" / "02_meme_style"
RAW = HERE / "raw"
OUT = HERE

# ---------------------------------------------------------------- 读取
def load_pairs():
    pairs = []
    for name in ("train.jsonl", "validation.jsonl"):
        path = RAW / name
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            msgs = obj.get("messages") or []
            user = asst = None
            for i, m in enumerate(msgs):
                if m.get("role") == "user" and user is None:
                    user = m.get("content") or ""
                elif m.get("role") == "assistant" and user is not None and asst is None:
                    asst = m.get("content") or ""
            if user is None or asst is None:
                continue
            pairs.append((user.strip(), asst.strip(), name))
    return pairs


# ---------------------------------------------------------------- 过滤
NOISE = re.compile(
    r"(https?://|www\.|tieba\.baidu|加微|加V|加v|微信|vx|VX|威信|QQ|qq号|代购|刷单|兼职|"
    r"优惠券|公众号|拼多多|淘宝|下单|扫码|私信|下载app|APP下载|广告|微商|引流)"
)
FORMAL = re.compile(
    r"(建议|推荐|可以尝试|需要注意|首先|其次|总之|方法如下|步骤如下|技巧|"
    r"总结|核心|关键点|分三步|具体来说|一方面|另一方面)"
)
ENUM = re.compile(r"[1-9１-９][）)\.、]")
EMOJI_ONLY = re.compile(r"^[\s\W_]+$", re.UNICODE)
EMOJI = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\u200b-\u200f\ufeff]")


def clean_text(s: str) -> str:
    s = CTRL.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


def is_generic_ai_answer(a: str) -> bool:
    """识别与「网梗风格」无关的通用 AI 长回答。"""
    if len(a) >= 150:
        return True
    if len(a) >= 100 and FORMAL.search(a):
        return True
    if len(a) >= 80 and ENUM.search(a) and a.count("\n") == 0:
        return True
    return False


def valid_pair(u: str, a: str) -> bool:
    if not u or not a:
        return False
    if len(u) > 300 or len(a) > 400:
        return False
    if EMOJI_ONLY.match(u) or EMOJI_ONLY.match(a):
        return False
    if NOISE.search(u) or NOISE.search(a):
        return False
    if is_generic_ai_answer(a):
        return False
    # 以「用户重复提问 + 回复重复」等方式的近重复在 chunk 内检查
    return True


# ---------------------------------------------------------------- 主题分桶
THEMES = OrderedDict([
    ("职场打工", ["老板", "领导", "同事", "加班", "上班", "工作", "入职", "面试", "公司", "年会",
                "ppt", "PPT", "简历", "辞职", "开会", "会议", "团建", "甲方", "乙方", "打工人",
                "打工", "实习", "职场", "工资", "裁员", "绩效", "KPI", "汇报", "方案", "需求", "工位"]),
    ("校园学习", ["作业", "考试", "老师", "上课", "学校", "学生", "大学", "期末", "复习", "学习",
                "数学", "题", "论文", "毕业", "军训", "高考", "同学", "班主任", "导师", "成绩",
                "宿舍", "专业", "考研", "补课", "家长会"]),
    ("恋爱情感", ["相亲", "女朋友", "男朋友", "男友", "女友", "暗恋", "表白", "恋爱", "分手",
                "前任", "对象", "喜欢", "暧昧", "结婚", "老公", "老婆", "约会", "告白", "情侣",
                "单身", "男友", "女友", "暗恋", "相亲对象"]),
    ("家庭亲戚", ["我妈", "我爸", "父母", "家里", "亲戚", "奶奶", "爷爷", "弟弟", "妹妹",
                "哥哥", "姐姐", "孩子", "娃", "儿子", "女儿", "婆婆", "岳母", "家人", "爸妈",
                "老公", "老婆", "姑姑", "舅舅"]),
    ("吃喝美食", ["吃", "饭", "外卖", "奶茶", "火锅", "美食", "菜", "食堂", "零食", "咖啡",
                "烧烤", "探店", "早餐", "宵夜", "辣", "甜", "餐厅", "口味", "饿", "饮料",
                "可乐", "水果", "炸鸡"]),
    ("购物消费", ["买", "价格", "贵", "便宜", "淘宝", "购物", "快递", "衣服", "护肤", "鞋",
                "优惠", "消费", "退货", "客服", "卖家", "下单", "直播间", "包", "化妆品",
                "穿搭", "牌子", "打折", "超市"]),
    ("游戏电竞", ["游戏", "打游戏", "账号", "段位", "王者", "原神", "队友", "开黑", "上分",
                "电竞", "副本", "氪金", "抽卡", "外挂", "挂机", "王者荣耀", "吃鸡", "皮肤"]),
    ("追星影视", ["明星", "偶像", "粉丝", "演唱会", "爱豆", "电影", "综艺", "剧", "演员",
                "导演", "春晚", "热搜", "塌房", "追星", "电视剧", "CP", "电影", "票房"]),
    ("网络流量", ["网红", "视频", "直播", "评论区", "博主", "点赞", "B站", "抖音", "小红书",
                "营销号", "弹幕", "算法", "平台", "流量", "网暴", "UP主", "网友", "屏幕"]),
    ("宠物动物", ["猫", "狗", "宠物", "仓鼠", "鸟", "鱼", "动物园", "铲屎", "主子", "喵", "汪"]),
    ("身体健康", ["减肥", "熬夜", "失眠", "医院", "医生", "生病", "感冒", "头发", "体重",
                "健身", "体检", "牙", "眼睛", "过敏", "疼", "生病", "睡眠", "养生"]),
    ("生活日常", ["睡觉", "起床", "地铁", "天气", "手机", "充电", "空调", "下雨", "租房",
                "搬家", "室友", "邻居", "理发", "洗澡", "公交", "周末", "假期", "房间"]),
    ("情绪发疯", ["崩溃", "生气", "焦虑", "累", "烦", "郁闷", "哭", "笑", "害怕", "内耗",
                "emo", "无语", "离谱", "社死", "尴尬", "窒息", "心态", "情绪"]),
    ("运动健身", ["篮球", "NBA", "足球", "球", "运动", "健身", "跑步", "三分", "投篮", "比赛",
                "球场", "打球", "赛季", "奥运", "冠军"]),
    ("音影动漫", ["歌", "mv", "MV", "专辑", "动漫", "台词", "番剧", "漫画", "剧本", "配音",
                "主唱", "乐队", "影院", "新歌", "封面"]),
    ("社交人际", ["朋友圈", "好友", "朋友", "兄弟", "闺蜜", "聊天", "群聊", "聚会", "生日",
                "礼物", "社交", "私信", "微信", "联系人", "搭子", "网友"]),
    ("抽象玩梗", ["抽象", "玩梗", "牢大", "整活", "哈基米", "奶龙", "已读乱回", "梗",
                "发疯", "搞笑", "段子", "表情包", "沙雕", "离谱"]),
    ("数码科技", ["电脑", "蓝屏", "wifi", "WiFi", "文件", "软件", "app", "系统", "内存",
                "硬盘", "AI", "人工智能", "机器人", "程序员", "代码"]),
])


def theme_of(text: str) -> str:
    for theme, kws in THEMES.items():
        for kw in kws:
            if kw in text:
                return theme
    return "杂谈其他"


# ---------------------------------------------------------------- 组块
MIN_LEN = 80
MAX_LEN = 800
MAX_PAIRS = 6
TARGET_PAIRS = 4


def _pack(items):
    """把同一主题桶的对话对切成 4 组/条的 chunk；不足 3 组的尾部并入前一块。"""
    groups = [items[i:i + TARGET_PAIRS] for i in range(0, len(items), TARGET_PAIRS)]
    if len(groups) >= 2 and len(groups[-1]) < 3:
        tail = groups.pop()
        if len(groups[-1]) + len(tail) <= MAX_PAIRS:
            groups[-1] = groups[-1] + tail
        else:
            groups.append(tail)
    # 超长兜底：单块超过 MAX_LEN 时再拆
    final = []
    for g in groups:
        cur = []
        for pair in g:
            pair_len = len(pair[0]) + len(pair[1]) + 12
            if cur and sum(len(u) + len(a) + 12 for u, a in cur) + pair_len > MAX_LEN:
                final.append(cur)
                cur = []
            cur.append(pair)
        if cur:
            final.append(cur)
    return final


def build_chunks(pairs):
    buckets = OrderedDict((t, []) for t in THEMES)
    buckets["杂谈其他"] = []
    seen = set()
    for u, a, src in pairs:
        key = (u, a)
        if key in seen:
            continue
        seen.add(key)
        buckets[theme_of(u + a)].append((u, a))

    chunks = []
    for theme in list(THEMES.keys()) + ["杂谈其他"]:
        for group in _pack(buckets[theme]):
            chunks.append(render(group))
    return chunks


def render(pairs) -> str:
    parts = []
    for u, a in pairs:
        parts.append(f"用户：{u}\n回复：{a}")
    return "对话：\n" + "\n\n".join(parts)


# ---------------------------------------------------------------- 输出
def main():
    pairs = load_pairs()
    print(f"原始对话对: {len(pairs)}")
    good = [(u, a, s) for (u, a, s) in pairs if valid_pair(u, a)]
    print(f"过滤后对话对: {len(good)}")
    print("来源分布:", Counter(s for _, _, s in good))

    chunks = build_chunks(good)
    # 去重 + 长度兜底
    seen, out = set(), []
    for c in chunks:
        if c in seen:
            continue
        if len(c) > 1200:
            continue
        if len(c) < MIN_LEN:
            continue
        seen.add(c)
        out.append(c)
    print(f"chunks: {len(out)}")
    lens = [len(c) for c in out]
    print(f"len min={min(lens)} avg={sum(lens)//len(lens)} max={max(lens)}")

    with (OUT / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for i, text in enumerate(out):
            fh.write(json.dumps({"id": i, "text": text}, ensure_ascii=False) + "\n")

    tz = timezone(timedelta(hours=8))
    manifest = {
        "kb_name": "网梗对话风格库",
        "description": "抖音/小红书/B站评论区的网梗对话风格语料，学习「用户抛梗—回复接梗」的中文互联网语气。",
        "emoji": "💬",
        "source_url": "https://huggingface.co/datasets/GaryYang123/zh-meme-sft-8k",
        "source_license": "见上游 HF 数据集页说明 / 仅限自用",
        "language": "zh-CN",
        "num_chunks": len(out),
        "built_at": datetime.now(tz).isoformat(timespec="seconds"),
        "builder": "corpus-meme-bar",
        "notes": (
            "数据源 GaryYang123/zh-meme-sft-8k（train.jsonl 7377 条 + validation.jsonl 868 条，共 8245 组对话）。"
            f"清洗后保留 {len(good)} 组：去掉 URL/联系方式/广告、纯符号、空串、过长且带条列结构的通用 AI 式回答（>=150 字或含「建议/推荐/1）…」的书面回答）、重复对。"
            "按 18 个粗粒度主题（职场/校园/恋爱/吃喝/游戏/追星/网络/宠物/健康/日常/情绪/运动/音影/社交/玩梗/数码等）分桶，桶内每 4–6 组合并为 1 条 chunk，"
            "同一 chunk 内语境相近；原文语气与口语（含 emoji）原样保留，不做书面化改写。"
            "已知局限：源数据混有少量通用问答，已按长度+句式启发式过滤，可能残留少量非梗回答；"
            "validation 集与 train 集风格略有差异，未做重新划分。"
        ),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("manifest written")


if __name__ == "__main__":
    main()
