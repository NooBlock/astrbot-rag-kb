# astrbot-rag-kb — 中文互联网梗 RAG 语料库（AstrBot 知识库）

给中文聊天机器人补上「梗、黑话、社区语气」的 RAG 语料工程：**5 个按层次组织的中文互联网语料库**，已整理成可直接导入 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 内置知识库（v3.5.13 起提供）的 `chunks.jsonl`，并附带构建、导入、校验脚本与完整使用文档。导入脚本只在 **v4.29.3** 的 `/api/v1` 接口上验证过。

- 合计 **4544 个 chunk**；验证环境 AstrBot **v4.29.3** + `Qwen/Qwen3-Embedding-8B`（1024 维，OpenAI 兼容接口）。
- 语料来源均为**公开数据集 / 公开网页的二次清洗与结构化**，原始抓取文件（`raw/`，第三方网页与数据集原文）不在本仓库发布。
- 第三方语料的许可状态多为「未声明 / 仅限自用」，**商用与再分发前请自行核对上游许可**，详见[许可与合规](wiki/许可与合规.md)。

> 本仓库的 `LICENSE` 只覆盖**本项目的代码与文档**，不覆盖 `corpora/` 下的第三方语料，也不对其授予任何许可。

## 它解决什么问题

通用对话模型对中文互联网的**新梗、圈层黑话、社区语气**理解有限：问「尊嘟假嘟是什么意思」「狐坦是谁」往往答非所问，或者用书面腔复述。把这些写进人格提示词既臃肿又容易过时，而 RAG 可以按需检索：

1. 用户问到一个梗时，从知识库召回**带释义、出处、语境**的片段；
2. 模型模仿语料里的**说话方式和语气**，而不是背诵语料；
3. 资料更新时只重建知识库，不必改人格与代码。

本项目按「**核心释义层 → 风格语料层 → 社区风格层 →（可选）动态更新层**」分层建库，让不同性质的语料各归其位，避免把所有梗混进一个大池子导致语义互相稀释。分层依据与字段约定见 [SPEC.md](SPEC.md)。

## 知识库一览

| 层 | 知识库 | emoji | chunk 数 | 数据来源 | 许可状态 |
| --- | --- | --- | ---: | --- | --- |
| 核心释义层 | **网络流行语释义库** | 🗣️ | 1219 | [SCUNLP/Buzzword](https://github.com/SCUNLP/Buzzword)（Cheer，ACL 2025），1183 个词条全量 | 上游无 LICENSE，研究/自用；再分发需授权并引用论文 |
| 风格语料层 | **网梗对话风格库** | 💬 | 1804 | [HF: GaryYang123/zh-meme-sft-8k](https://huggingface.co/datasets/GaryYang123/zh-meme-sft-8k)，清洗后 7228 组对话全量 | 上游未单独声明，仅限自用 |
| 社区风格层 | **弱智吧语料库** | 🧠 | 1320 | [HF: kirp/ruozhiba-raw](https://huggingface.co/datasets/kirp/ruozhiba-raw)（固定种子抽 4800 条标题）+ [HF: LooksJuicy/ruozhiba](https://huggingface.co/datasets/LooksJuicy/ruozhiba)（1434 组问答全量） | 贴吧用户原创内容；仅限自用，避免商用/原文转载 |
| 社区风格层 | **V吧黑话库** | 🎭 | 120 | 知乎《v吧常见黑话大全》（节选）+ [萌娘百科《虚拟UP主用语与梗》](https://zh.moegirl.org.cn/虚拟UP主用语与梗)，逐条标注出处 | 引用型二次整理；版权归原作者/站点，萌百内容不可商用 |
| 社区风格层 | **地狱笑话库** | 💀 | 81 | 煎蛋「一些地狱笑话」系列、搜狐、知乎文本答案、GitHub `ChaokunChang/Joke-Factory` 段子筛选 | 各来源版权归原作者/站点；仅限自用，含冒犯性内容 |
| 动态更新层 | （未建库） | — | — | B 站热词接口实测只有裸热词、无释义（且受限流），按「不编造」原则跳过 | — |
| **合计** | | | **4544** | | |

构建快照：2026-10-26 02:59–03:20（+08:00）。每个库的准确条数、来源 URL、构建方式、已知局限见 `corpora/<库>/manifest.json` 与 `corpora/<库>/README.md`，逐库详解见[语料说明](wiki/语料说明.md)。

## 快速开始（3 步）

前提：可运行的 **AstrBot**（本项目在 **v4.29.3** 上验证；内置知识库自 v3.5.13 起提供，脚本依赖 v4.18.0 起的 `/api/v1`）和一个 **OpenAI 兼容的 embedding 模型**。语料校验不需要 AstrBot。

```bash
# 1) 获取语料并校验格式
git clone https://github.com/NooBlock/astrbot-rag-kb.git
cd astrbot-rag-kb
python tools/validate_corpus.py --all corpora

# 2) 在 AstrBot WebUI「模型提供商 → 嵌入」中配置好 embedding，并记下它的 id
#    （脚本新建库默认用 provider id `openai_embedding`；id 不同则先在 WebUI 建同名空库，
#      本项目快照为 1024 维，换模型须重建库）

# 3) 建库 + 导入预切块语料，再验证
python -m pip install -r tools/requirements.txt
python tools/build_kbs.py   --config /path/to/astrbot/data/cmd_config.json
python tools/verify_kbs.py  --config /path/to/astrbot/data/cmd_config.json
```

> 上面的 `python` 指 **AstrBot 所在环境的 Python 3.12**（Windows：`astrbot\.venv\Scripts\python.exe`；Linux/macOS：`astrbot/.venv/bin/python`）。Windows 控制台建议先执行 `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"`。
>
> `--config` 指向 AstrBot 数据目录下的 `cmd_config.json`（内含 `dashboard.jwt_secret` 等敏感信息，**切勿提交或外传**），也可用环境变量 `ASTRBOT_CONFIG` 指定；服务端地址默认 `http://127.0.0.1:6185/api/v1`，可用 `ASTRBOT_BASE_URL` 覆盖。

## 目录结构

```
astrbot-rag-kb/
├─ README.md                     # 本文件
├─ SPEC.md                       # 语料构建规范（分层、格式、命名约定）
├─ LICENSE                       # MIT，仅覆盖本仓库代码与文档，不覆盖第三方语料
├─ .gitignore                    # 忽略 __pycache__、原始数据 raw/ 等
├─ corpora/                      # 语料（每个库一个目录）
│  ├─ README.md                  # corpora 目录说明与一览
│  ├─ 01_cheer_terms/            # 网络流行语释义库（核心释义层）
│  ├─ 02_meme_style/             # 网梗对话风格库（风格语料层）
│  ├─ 03_ruozhiba/               # 弱智吧语料库（社区风格层）
│  ├─ 04_vbar/                   # V吧黑话库（社区风格层）
│  ├─ 05_hell/                   # 地狱笑话库（社区风格层）
│  │  ├─ chunks.jsonl            # 每行一个 {"id": int, "text": str}
│  │  ├─ manifest.json           # 知识库元信息（导入时自动读取）
│  │  └─ README.md               # 该库的来源、构建方法、局限
│  └─ _state/imported.json       # 构建/导入状态：kb_id、条数、chunks.jsonl 的 sha256
├─ tools/
│  ├─ README.md                  # tools 使用说明
│  ├─ requirements.txt           # requests / PyJWT
│  ├─ kb_client.py               # AstrBot /api/v1 知识库客户端（本机 JWT 签发）
│  ├─ build_kbs.py               # 批量建库 + 导入 + 校验（按内容哈希幂等）
│  ├─ verify_kbs.py              # 统计 + 检索冒烟测试
│  └─ validate_corpus.py         # 语料格式自检（单个目录 / --all 批量）
├─ scripts/build/<corpus>/       # 各库的来源下载与清洗脚本（参考用，不含 raw 数据）
├─ docs/
│  └─ 数据字典.md                # chunks.jsonl / manifest.json 字段规范
└─ wiki/                         # 使用文档（从 Home.md 开始）
   ├─ Home.md
   ├─ 快速开始.md
   ├─ 语料说明.md
   ├─ 导入到 AstrBot.md
   ├─ 维护与更新.md
   ├─ FAQ.md
   └─ 许可与合规.md
```

原始抓取数据（`raw/`）**不在本仓库发布**。`scripts/build/` 里的脚本记录了当时的下载与清洗逻辑，**仅作参考**：需先按脚本中的上游 URL 自行下载原始数据，并按你的目录结构调整脚本内的路径，不保证开箱即跑。

## 复现要求

| 项 | 要求 | 说明 |
| --- | --- | --- |
| Python | **3.12**（AstrBot 要求 `>=3.12`） | 校验脚本只用标准库；导入/验证脚本需 `requests` + `PyJWT`（AstrBot 的 venv 通常已自带，独立环境执行 `pip install -r tools/requirements.txt`） |
| AstrBot | **v4.29.3**（内置知识库自 v3.5.13 起提供） | 本项目只在该版本的 `/api/v1` 上验证，其他版本接口可能有差异 |
| 嵌入模型 | 任意 OpenAI 兼容 embedding 接口 | 本仓快照使用 SiliconFlow `Qwen/Qwen3-Embedding-8B`（1024 维）；换模型等于换向量空间，必须重建知识库 |
| 对话模型（可选） | 支持函数调用（工具调用） | 只有开启 Agentic 知识库检索时才需要 |
| 网络 | 能访问 AstrBot WebUI 与 embedding 服务 | 导入过程会把 chunk 文本发给 embedding 服务，注意数据边界 |

> `chunks.jsonl` 与 AstrBot 无绑定，任何向量库（LangChain / Dify / LlamaIndex / 自研）都可直接读取，见 [FAQ](wiki/FAQ.md#other-frameworks)。

## 安全与合规声明

- **语料是公开数据的二次整理，不是官方词典。** 释义可能过时、有偏差；对话语气语料含夸张、自嘲、互怼，个别内容带冒犯性。
- **许可未明**：多数上游未声明开放许可。本仓库仅作学习、研究与个人自用参考；**商用、公开部署、再分发前请逐一核对上游许可**，必要时取得授权。详见[许可与合规](wiki/许可与合规.md)。
- **地狱笑话库（💀）默认不应主动使用**：仅作受控的风格语料，上线前必须在模型侧配置安全过滤，避免生成涉及真实受害者、地域、疾病、未成年人的内容。详见[语料说明](wiki/语料说明.md)与 [FAQ](wiki/FAQ.md#safety-filter)。
- 请勿把语料用于骚扰、人肉、歧视、违法内容生成，或绕过平台审核；使用者对最终输出负责。
- `cmd_config.json`、任何 API Key / JWT Secret 都不要提交到仓库；本文档与脚本示例中的地址、Key 均为占位符。

## 相关文档

| 文档 | 内容 |
| --- | --- |
| [SPEC.md](SPEC.md) | 原始语料构建规范：分层、目录与字段约定 |
| [wiki/Home.md](wiki/Home.md) | 文档导航与阅读顺序 |
| [wiki/快速开始.md](wiki/快速开始.md) | 从零到可用：环境、建库、导入、验证、排错 |
| [wiki/语料说明.md](wiki/语料说明.md) | 5 个库逐条说明：来源、清洗、抽样、质量、局限 |
| [wiki/导入到 AstrBot.md](wiki/导入到%20AstrBot.md) | WebUI / 脚本两种导入路径，以及让知识库参与对话的配置 |
| [wiki/维护与更新.md](wiki/维护与更新.md) | 新增语料、重建、换模型、备份迁移、定时更新 |
| [wiki/FAQ.md](wiki/FAQ.md) | 条数不符、检索不到、乱码、JWT、维度、商用等常见问题 |
| [wiki/许可与合规.md](wiki/许可与合规.md) | 逐库许可状态、再分发风险、署名与下架方式 |
| [docs/数据字典.md](docs/数据字典.md) | `chunks.jsonl` / `manifest.json` 字段与校验规则 |

> **这次建设的完整过程**（为什么分层、抓取与清洗踩了哪些坑、导入时怎么处理重复 chunk）记录在同批发布的
> **[`astrbot-worklog`](https://github.com/NooBlock/astrbot-worklog)** 仓库的 `2026-10-26.md` 里，
> 适合想了解语料工程决策过程的人。

## 致谢

- [AstrBot](https://github.com/AstrBotDevs/AstrBot)：内置知识库与 `/api/v1` 接口。
- [SCUNLP/Buzzword](https://github.com/SCUNLP/Buzzword)（Cheer）及论文作者：网络流行语释义数据。
- [GaryYang123/zh-meme-sft-8k](https://huggingface.co/datasets/GaryYang123/zh-meme-sft-8k)、[kirp/ruozhiba-raw](https://huggingface.co/datasets/kirp/ruozhiba-raw)、[LooksJuicy/ruozhiba](https://huggingface.co/datasets/LooksJuicy/ruozhiba)：风格与社区语料。
- 知乎、萌娘百科、煎蛋、搜狐等公开页面的作者与整理者。

> 若你是上述内容的权利人并希望下架相关内容，请通过仓库 Issue 联系维护者，我们会移除对应语料。
