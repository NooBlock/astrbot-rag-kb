# 大肥鱼 RAG 语料库构建规范（SPEC）

本文件是「中文互联网梗 / 黑话 RAG 语料库」的构建规范（从原始工作区导出，绝对路径与凭据已替换）。
来源对话：https://chat.deepseek.com/share/vlkej01r7djnl9curb
对话建议采用**分层建库**，落到 5 个（可选第 6 个）知识库：

| 目录 | 知识库名 | 层 | 内容来源 |
| --- | --- | --- | --- |
| `01_cheer_terms` | 网络流行语释义库 | 核心释义层 | Cheer / SCUNLP-Buzzword（1127+ 条，含释义、例句、ground truth） |
| `02_meme_style` | 网梗对话风格库 | 风格语料层 | `GaryYang123/zh-meme-sft-8k`（抖音/小红书/B站评论对话） |
| `03_ruozhiba` | 弱智吧语料库 | 社区风格层 | 弱智吧数据集（`wisdomsbar` / ModelScope `AI-ModelScope/ruozhiba` / HF `kirp/ruozhiba-raw`） |
| `04_vbar` | V吧黑话库 | 社区风格层 | 知乎《v吧常见黑话大全》等公开资料 + 精标词条（小而准） |
| `05_hell` | 地狱笑话库 | 社区风格层 | 公开中文黑色幽默/地狱笑话语料筛选 + 精标（带安全标注） |
| `06_bili_terms` | B站热词图鉴 | 动态更新层 | B 站公开「名词解释 / 热词图鉴」接口（可选） |

## 每个语料目录必须产出

```
<dir>/
  chunks.jsonl    # 必需。每行一个 JSON：{"id": <int>, "text": "<已可嵌入的完整片段>"}
  manifest.json   # 必需。见下方字段
  README.md       # 必需。来源、许可、构建方法、注意事项
  raw/            # 可选。原始下载数据（可保留小样本，大文件请删除）
```

### chunks.jsonl 规则

- 编码 UTF-8（无 BOM），每行一个 JSON 对象，字段：`id`（自增整数）、`text`（字符串）。
- `text` 必须**自包含**：单独被检索出来也能读懂，不能只有「666」这样的裸词，需带词条名/语境。
- 单条 `text` 长度建议 80–800 字符；不要整篇长文塞一条（embedding 语义会被稀释）。
- 相邻重复内容必须去重（完全相同的 `text` 只保留一条）。
- 不要包含 HTML 标签、Markdown 表格分隔行、过多空白；保留 emoji 可以。
- 总量建议：
  - `01_cheer_terms`：全部词条（约 1100–1200 条）
  - `02_meme_style`：1500–2500 条（把多条短对话合并成一条，每条包含 3–6 组「用户/回复」）
  - `03_ruozhiba`：800–1500 条（每条包含 3–6 个问答对）
  - `04_vbar`：120–300 条（每条 1 个词条，含释义/出处/用法）
  - `05_hell`：80–200 条（每条 1 个笑话 + 安全提示）
  - `06_bili_terms`：200–1000 条（可选）

### manifest.json 字段

```json
{
  "kb_name": "网络流行语释义库",
  "description": "一句话说明（会显示在 AstrBot WebUI）",
  "emoji": "🗣️",
  "source_url": "https://github.com/SCUNLP/Buzzword",
  "source_license": "见上游仓库 LICENSE / 仅限自用",
  "language": "zh-CN",
  "num_chunks": 1183,
  "built_at": "2026-10-26Txx:xx:xx+08:00",
  "builder": "teammate-name",
  "notes": "构建方式、抽样策略、已知局限"
}
```

## 环境与网络

- Python：`python`（已含 requests / httpx / beautifulsoup4 / openai）。
- 外网如需代理：请自行设置 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量（无代理可直连）。
- 直连 GitHub raw / huggingface.co / hf-mirror.com 可用；知乎直连 403，B 站接口需请求头/可能 412。
- 控制台是 GBK：脚本内 `print` 中文请先设置 `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"`，或写文件后再读。
- 所有产物**只能写自己任务目录**，不要改别人的目录、不要动 `astrbot/` 源码与配置。

## 自检（提交前必须跑）

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
& "python" ".\tools\validate_corpus.py" "<目录>"
```

脚本会检查：JSON 合法、字段齐全、无空串、无重复、长度区间、manifest 与条数一致。

## 交付

完成后向 Lead 汇报：目录、条数、来源 URL、抽样策略、遗留问题（不要写任何 *_SUMMARY.md 之类的报告文件到 astrbot 仓库）。
