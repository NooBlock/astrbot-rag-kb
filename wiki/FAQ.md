# FAQ

按出现频率排序。命令均在仓库根目录执行，`<ASTRBOT_DATA>` 指 AstrBot 的 `data/` 目录，`python` 指 AstrBot 环境的 Python 3.12。

---

<a id="count-mismatch"></a>

## 1. 导入后 chunk 数对不上（为什么不是 1219 / 1804 / …）

先分清三个数字：

- `chunks.jsonl` **行数**：语料条数，例如 01 库 1219 条；
- 知识库 **chunk_count**：导入后的分块数，预切块导入下应**等于**行数；
- **doc_count**：文档数，脚本按每 800 条一个文档分片，所以 1219 条 → 2 个文档、1804 条 → 3 个文档，与 chunk 数无关。

如果 `chunk_count` 真的不等于行数：

| 原因 | 处理 |
| --- | --- |
| 用 WebUI 上传了文本文件（被按 512 字符重切） | 改用 `tools/build_kbs.py` 预切块导入 |
| 上次导入中途失败，留下孤儿 chunk | `python tools/build_kbs.py --config <ASTRBOT_DATA>/cmd_config.json --only <目录> --force` |
| `manifest.json` 的 `num_chunks` 与文件不一致 | 先 `python tools/validate_corpus.py <目录>` 修正 |
| 对比的是「文档管理」页显示的数字 | 那是文档数/分块合计，先按上面区分 |

---

<a id="retrieval-miss"></a>

## 2. 检索不到相关内容 / 模型说「没有找到相关知识」

按顺序排查：

1. **`kb_names` 是否为空或库名拼错**：配置里的名称必须与知识库名完全一致（含 emoji 不需要，名称文字要一致）。
2. **是否只开了 Agentic 而 `kb_names` 为空**：工具内部按 `kb_names`/会话级 kb_ids 确定范围，空时只返回 “No relevant knowledge found.”。**两个都要设**，见[导入到 AstrBot § C2](导入到%20AstrBot.md#c-如何让知识库真正参与对话)。
3. **会话级 kb_ids 覆盖了全局配置**：检查聊天页会话设置/自定义规则，清空后保存可恢复全局。
4. **先在 WebUI「知识库检索」标签测试**：如果这里也搜不到，是语料/分块问题，不是对话配置问题。
5. **换一个更明确的问题**：黑话用词条原名检索（如「aewt」），不要用一整句闲聊。
6. **embedding 是否可用、维度是否与建库时一致**：提供商被改过模型/维度会直接破坏索引。
7. **调大召回**：`kb_final_top_k` 默认 5，可临时调到 8–10 观察，但会增加 prompt 体积。
8. **模型忽略资料**：在人格里补充「优先依据检索到的资料回答，资料不足时明确说没有找到」。

---

<a id="garbled"></a>

## 3. 建库 / 导入后中文乱码

| 场景 | 原因 | 处理 |
| --- | --- | --- |
| 命令行输出乱码 | Windows 控制台默认 GBK | `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"` |
| 导入后 chunk 显示乱码 | 上传/生成的文件不是 UTF-8 | 语料必须是 **UTF-8 无 BOM**；用 `validate_corpus.py` 检查 |
| 文件被记事本/Excel 反复保存 | 编码被改成 ANSI/GBK 或加了 BOM | 用 VS Code「UTF-8（无 BOM）」另存；`chunks.jsonl` 首字节不应是 `EF BB BF` |
| PowerShell 重定向生成的文件带 BOM | `>`/`Out-File` 默认行为 | 用 Python 写文件，`encoding="utf-8"`，不要用 shell 重定向 |

验证方法：

```bash
python tools/validate_corpus.py corpora/01_cheer_terms
```

若 JSON 解析失败或条数对不上，会直接报错。

---

<a id="jwt-expired"></a>

## 4. JWT 过期或 401

脚本鉴权流程：读 `cmd_config.json` 的 `dashboard.jwt_secret` → 本机签发 **1 小时有效**的 HS256 JWT → `Authorization: Bearer <JWT>`。每次运行脚本都会重新签发，所以正常不会因「过期」失败。仍报 401 时：

- `--config` / `ASTRBOT_CONFIG` 指向的文件不对（比如指到了备份文件、或别的 AstrBot 实例）；
- `dashboard.jwt_secret` 被改过（重装、重置配置、迁移数据后常见）；
- 系统时钟偏差过大；
- AstrBot 不是你以为的那个实例（端口不同 → 用 `ASTRBOT_BASE_URL` 指对）。

处理：确认 `--config` 指向**正在运行的那个实例**的 `data/cmd_config.json`，重启 AstrBot 后再跑。**不要**把该文件或其中的 secret 发给别人。

> 注意：`abk_` 开头的开发者 API Key 不能用来调知识库接口（scope 列表无 `kb`），会返回 403，不用去 WebUI 生成 Key。

---

<a id="embedding-dim"></a>

## 5. 报 embedding 维度不匹配 / 检索结果很差

知识库创建时绑定了 embedding 模型与维度，**之后不能换**。以下操作都会导致不兼容：

- 把提供商里的模型名改成另一个模型；
- 把「向量维度」改成另一个数字；
- 迁移到另一台机器，但 embedding 服务换了模型。

只改维度字段并不能转换已有向量。正确处理：新建一个正确维度的提供商 → 用新提供商重建知识库 → 全量导入。详见[维护与更新 § 更换 embedding 模型的后果](维护与更新.md#更换-embedding-模型的后果)。

---

<a id="astrbot-version"></a>

## 6. AstrBot 版本不同，菜单/命令/接口对不上

- 内置知识库自 **v3.5.13** 起提供；本项目在 **v4.29.3** 上验证，导入脚本依赖 v4.18.0 起的 `/api/v1`。
- 版本过低：没有「知识库」菜单，或没有 `/api/v1`（HTTP API 从 v4.18.0 起提供）→ 升级 AstrBot；也可以只用 `chunks.jsonl` 做自己的 RAG。
- 版本更新后：菜单文案、配置分组可能变化，但 `kb_names` / `kb_agentic_mode` 等配置键在较新版本中保持稳定；以你版本 WebUI 的「知识库」相关配置为准。
- 旧插件版知识库（`knowledge-base-old`）与本项目接口不同，不要混用。

---

<a id="commercial-use"></a>

## 7. 语料能商用吗？能公开发布吗？

**不能默认可以。** 5 个库的上游许可多数未声明：

- 01 上游仓库**没有 LICENSE**，是研究数据集；
- 02、03 来自 HuggingFace 公开数据集，但上游未明确许可；
- 04、05 是知乎/萌百/煎蛋/搜狐等网页内容 + 公开段子集的二次整理，版权归原作者/站点。

本项目按「学习/自用」处理，不主张对第三方语料的权利。商用、公开部署或以任何形式再分发前，请自行核对上游条款并取得必要授权。详见[许可与合规](许可与合规.md)。

---

<a id="other-frameworks"></a>

## 8. 能否用于其他框架（LlamaIndex / LangChain / Dify）

可以。`chunks.jsonl` 是普通 JSONL，一行一条 `{"id": int, "text": str}`，与 AstrBot 无绑定。

**LangChain**：

```python
import json
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS  # 或你使用的向量库

docs = []
with open("corpora/01_cheer_terms/chunks.jsonl", encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if line:
            obj = json.loads(line)
            docs.append(Document(page_content=obj["text"], metadata={"id": obj["id"], "kb": "01_cheer_terms"}))

# embeddings 用你自己的实现（OpenAI 兼容接口 / 本地模型均可）
vectorstore = FAISS.from_documents(docs, embedding=your_embeddings)
```

**Dify**：新建知识库 → 导入为文本/自定义分段；或对已有分段数据调用其 API。注意 Dify 会按自己的分段策略处理普通文本上传，若要保持预切块，需用「自定义分段/API 导入」。

**LlamaIndex**：用 `SimpleDirectoryReader` 读 `.jsonl` 不方便，建议直接把每行 `text` 写成单独的 `.txt`（或 `Document(text=...)` 列表），再建 `VectorStoreIndex`。

**通用注意**：

- 不要再把自包含的 chunk 切得很碎（例如按 200 字符硬切），会破坏「单独检索也能读懂」的设计；
- 不同库性质不同：释义库（01）适合问答检索，02/03/04 更像风格上下文，05 需安全过滤；
- 换 embedding 模型同样要重建全部向量。

---

<a id="corpus-stale"></a>

## 9. 语料过时了怎么办？能自动更新吗？

本仓库是 **2026-10 的静态快照**，新梗覆盖不到（尤其 01，以 2010s–2020s 语境为主）。工具支持幂等重建，但**不包含自动抓取**。

建议：按[维护与更新 § 动态更新层](维护与更新.md#动态更新层定时补充新梗)搭一条「搜索 → 结构化 → 去重 → 校验 → 入库」的周更流水线，单独建 `06_dynamic` 库，避免污染释义库。

---

<a id="safety-filter"></a>

## 10. 地狱笑话安全过滤怎么做

先明确：**05 地狱笑话库默认不应挂载**。如果确需使用（例如熟人小群的娱乐场景），至少做三层：

1. **配置层**：只给特定会话挂载该库；默认配置的 `kb_names` 不包含「地狱笑话库」；
2. **提示词层**：在人格/系统提示里写清边界，例如：

   ```text
   涉及真实悲剧、现实人物、未成年人、地域/民族/疾病/残障歧视的内容一律不生成；
   不主动使用黑暗幽默，仅在用户先玩梗且明确表示可以时，最多轻描淡写一句；
   对方表达不适时立刻停止并道歉。
   ```

3. **输出层**：在机器人回复发送前做关键词/正则过滤（真实事件名、地域歧视词、疾病羞辱词等），命中则替换为安全回复；AstrBot 可用插件或消息处理钩子实现。

另外：不要把该库用于公开群、直播间、未成年人可接触的场景；对外发布内容建议整体不用。任何过滤都只能降低风险，不能保证零事故，**使用者对输出负责**。

---

<a id="jsonl-upload"></a>

## 11. 为什么 WebUI 不能直接上传 `chunks.jsonl`？

v4.29.3 WebUI 支持上传的格式是 `.txt`、`.md`、`.markdown`、`.rst`、`.adoc`、`.pdf`、`.docx`、`.epub`、`.xls`、`.xlsx`，**不包括 `.jsonl`**。即使上传文本，WebUI 也会按知识库的分块参数（默认 512 字符 / 重叠 50）重新切分，破坏预切块设计。

正确做法：用 `tools/build_kbs.py` 直接调用 AstrBot 的**预切块导入**接口，一条 chunk 原样入库。WebUI 只用于建库、检查、检索测试与少量补录。详见[导入到 AstrBot](导入到%20AstrBot.md)。

---

<a id="missing-terms"></a>

## 12. 为什么没有「舰长 / 提督」或某个我知道的梗？

- **V吧黑话库**未收录「舰长/提督」：它们是 B 站直播「大航海」付费等级词，属平台机制而不是 V 吧黑话；构建时没有找到可引用的公开释义页，按「可追溯优先、不编造出处」原则暂缺。
- **01 释义库**的词条上限取决于上游数据集（1183 条），新梗与冷门梗覆盖有限。
- 其他库同理：只收可追溯来源的内容，宁可少收，不编造。

自行补充：按 [docs/数据字典.md](../docs/数据字典.md) 写 `chunks.jsonl` + `manifest.json`，然后 `build_kbs.py --only <目录>` 重建对应库（或新建 `06_*` 库）。

---

<a id="one-kb-only"></a>

## 13. 能只用一个库，或删掉某个库吗？

可以。建库不是全有全无：

- 只建/只导入需要的库：`python tools/build_kbs.py --config <ASTRBOT_DATA>/cmd_config.json --only 01_cheer_terms`；
- 不想要某个库：WebUI 删除知识库，并从配置 `kb_names` 中移除；对应的 `corpora/<库>/` 可以保留（便于以后恢复）或删除；
- 注意：删除知识库不可恢复，之后再建需要重新导入。

---

<a id="need-qq"></a>

## 14. 一定要用 AstrBot / QQ 机器人吗？

知识库功能是 AstrBot 的能力，要用它的内置知识库就得有 AstrBot。但这批语料本身是纯文本，不绑定任何平台：

- 用其他机器人框架：自己实现 RAG 或按上面的 LangChain/Dify 方式接入；
- 用其他 IM 平台：AstrBot 支持多平台适配，知识库配置与平台无关；
- 只想本地测试：用 `verify_kbs.py` 直接调检索接口，不需要接 QQ。

---

<a id="internal-files"></a>

## 15. 能把 `doc.db` / `index.faiss` 发给别人吗？

不建议。这些是 AstrBot 的运行时索引，和版本、embedding 模型、知识库 ID、内置数据结构强绑定，换环境极易损坏或不兼容。要分享成果，请分享 `corpora/`（`chunks.jsonl` + `manifest.json`），对方重新导入即可。备份/迁移请用 WebUI「备份管理」或按[维护与更新 § 备份与迁移](维护与更新.md#备份与迁移)操作。

---

<a id="local-embedding"></a>

## 16. 想用本地 embedding（Ollama / 本地模型）可以吗？

可以。AstrBot 支持 OpenAI 兼容接口与 Ollama 等本地服务，只要：

- API 地址能从 **AstrBot 所在环境**访问到（Docker 里的 `localhost` 指容器自己，不是宿主机）；
- 模型与维度填写正确（换模型必须重建知识库）；
- 本地模型的向量维度决定索引大小，显存/内存要够。

本地 embedding 不产生 API 费用，也没有内容外发顾虑，但建库速度取决于本机算力。
