# 导入到 AstrBot

把语料变成 AstrBot 知识库有两条路径：**WebUI 手动上传**（直观、会被重新分块）和**脚本预切块导入**（推荐、一条 chunk 原样入库）。本页也讲最后一步——怎么让知识库真正参与对话。

## 路径对比

| 维度 | A. WebUI 手动导入 | B. 脚本导入（`tools/build_kbs.py`） |
| --- | --- | --- |
| 操作 | 浏览器点选建库、上传文件 | 命令行，读 `manifest.json` 自动建库 |
| 是否保持预切块 | ❌ AstrBot 按自己的分块参数重切 | ✅ 一条 chunk 原样入库 |
| 能否直接上传 `chunks.jsonl` | ❌ 不在支持格式内 | ✅ 脚本读文件后走预切块接口 |
| 适合 | 少量补录、只建一两个库、没有 Python 环境 | 全量、可重复、可 CI 化 |
| 幂等 | 需手工删除旧文档 | 按 `chunks.jsonl` 的 sha256 自动跳过/重建 |

---

<a id="a-webui-手动导入"></a>

## A. WebUI 手动导入

### A1. 创建知识库

1. 侧边栏 → **知识库**；
2. 点 **创建知识库**；
3. 填名称（与 `manifest.json` 的 `kb_name` 一致，例如「网络流行语释义库」）、描述、emoji；
4. 选择**嵌入模型**（第 3 步配好的 provider）；
5. 点 **创建**。

注意事项：

- **嵌入模型选定后不可修改**。选错只能删库重建。
- 名称用于配置里的 `kb_names` 匹配，**后续改名要同步修改配置**。
- 可以重复 5 次，把 5 个库都建出来；也可以只建你需要的。

### A2. 上传文档

1. 打开刚创建的知识库 → **文档管理** → **上传文档**；
2. 保持在 **文件上传** 标签，拖入文件（可多选）；
3. 首次使用可保留分块/批处理默认值，点 **上传**；
4. 等待解析、分块、生成 embedding 完成，确认文档列表显示条数与分块数。

**v4.29.3 支持的上传格式**：`.txt`、`.md`、`.markdown`、`.rst`、`.adoc`、`.pdf`、`.docx`、`.epub`、`.xls`、`.xlsx`；界面标注单文件最大 128 MB。PDF 需包含可提取文本（纯扫描件不做 OCR）。

**关键限制：`.jsonl` 不在支持格式内。** 所以 WebUI 不能直接「上传 chunks.jsonl 并保持预切块」。如果只能用 WebUI：

- 把每个库的 chunk 文本合并成一个 `.md` / `.txt` 再上传。AstrBot 会按知识库的分块参数（默认 512 字符 / 重叠 50）重新切分，**条数会变**：原本精心控制的自包含片段可能被拆开或合并，检索质量与该库设计目标有差距。
- 这种做法只建议用于小库或临时验证；要还原设计效果，请用 B 路径。

> **不要手传内部产物**：`astrbot/data/knowledge_base/<kb_id>/` 下的 `doc.db`、`index.faiss` 是 AstrBot 的运行时索引文件，与版本、embedding 维度、库 ID 强绑定，直接复制/上传会损坏知识库。备份/迁移请用 WebUI 的「备份管理」，见[维护与更新](维护与更新.md#备份与迁移)。

### A3. 上传后检查

1. **文档管理** 里点开文档，看解析出的分块是否符合预期；
2. 打开知识库的 **知识库检索** 标签，输入一个语料里确实有的问题（如「尊嘟假嘟是什么意思」）；
3. 确认返回片段中确实有答案，再进入 C 步骤启用。

> 进阶：WebUI 登录后浏览器已带 JWT cookie，理论上可在控制台直接调 `POST /api/v1/knowledge-bases/{kb_id}/documents/import` 做预切块导入，但需要自行拼 `chunks` 数组，适合少量补录，不适合整库迁移。

---

<a id="b-脚本导入"></a>

## B. 脚本导入（预切块）

### B1. 原理

`tools/build_kbs.py` 不解析原始文档，而是直接调用 AstrBot 的**预切块导入接口**：

```text
读取 corpora/<库>/manifest.json + chunks.jsonl
  → 按 kb_name 查找知识库，不存在则创建
  → POST /api/v1/knowledge-bases/{kb_id}/documents/import
       {"documents": [{"file_name": "...", "file_type": "txt", "chunks": [...] }],
        "batch_size": 32, "tasks_limit": 3, "max_retries": 3}
  → 轮询 GET /api/v1/knowledge-bases/tasks/{task_id} 直到 completed
  → GET /api/v1/knowledge-bases/{kb_id}/stats 校验 chunk_count
  → 写入 corpora/_state/imported.json
```

每个库按 **800 条/文档** 分片导入，所以 `doc_count` 不一定等于 1（例如 1219 条会分成 2 个文档）。这个数字不影响检索，只影响文档管理的展示。

### B2. 鉴权

脚本用本机 JWT，不需要 WebUI 密码：

- JWT 用 `cmd_config.json` 里的 `dashboard.jwt_secret` 以 **HS256** 签发，claims 为 `{"username": ..., "iat": ..., "exp": ...}`，有效期 1 小时（脚本每次运行重新签）；
- 请求头 `Authorization: Bearer <JWT>`，调 `http://127.0.0.1:6185/api/v1`；
- **不要**用「设置 → OpenAPI」里创建的 `abk_` 开发者 API Key 调知识库接口：v4.29.3 的开发者 API Key scope 列表里没有 `kb`，会返回 403。

> `cmd_config.json` 含 `dashboard.jwt_secret` 等敏感信息，**只放本机、不要提交仓库或外发**。

### B3. 执行

```bash
# 依赖（AstrBot 的 venv 一般已自带）
python -m pip install -r tools/requirements.txt

# 全量 5 个库
python tools/build_kbs.py --config /path/to/astrbot/data/cmd_config.json

# 只建库不导入 / 只处理一个库 / 强制重建
python tools/build_kbs.py --config /path/to/astrbot/data/cmd_config.json --create-only
python tools/build_kbs.py --config <ASTRBOT_DATA>/cmd_config.json --only 01_cheer_terms
python tools/build_kbs.py --config <ASTRBOT_DATA>/cmd_config.json --force
```

可用环境变量代替参数：

| 变量 | 作用 |
| --- | --- |
| `ASTRBOT_CONFIG` | 等价于 `--config` |
| `ASTRBOT_BASE_URL` | 覆盖默认 `http://127.0.0.1:6185/api/v1` |

`--root` 默认是仓库下的 `corpora/` 目录（语料根目录本身），默认扫描其中以两位数字开头的语料目录；语料不在仓库内时用 `--root` 指定。

**关于 embedding provider id**：脚本新建知识库时固定使用 `openai_embedding`（`tools/kb_client.py` 的 `create_kb()` 默认参数）。若你的提供商 id 不同：先在 WebUI 建好同名空知识库再跑脚本（脚本会复用已有库），或修改 `kb_client.py` 中 `create_kb()` 的 `embedding_provider_id` 默认值。`--config` 未指定时脚本尝试读取当前目录下 `astrbot/data/cmd_config.json`。

### B4. 幂等语义（重复执行会怎样）

| 状态 | 脚本行为 |
| --- | --- |
| `imported.json` 中该库不存在 | 全量导入 |
| 已记录，且 `num_chunks` 与 `sha256` 都与当前 `chunks.jsonl` 一致 | **跳过**（秒级完成） |
| 已记录，但条数或哈希变了 | **删除旧库 → 重新创建 → 全量导入** |
| `--force` | 忽略记录，删库重建 |
| `--create-only` | 只建空库，不导入 |

为什么「改了内容就删库重建」而不是增量更新：预切块导入以「文档」为单位，删除单个文档后 AstrBot 的 `doc.db` 里可能遗留孤儿 chunk，导致 `chunk_count` 对不上；整库删除重建最干净。代价是要重新计算全部 embedding（见[维护与更新](维护与更新.md#增量与全量)）。

导入完成后脚本会用 `/stats` 校验 `chunk_count` 与期望一致；不一致会报错并非零退出。

### B5. 验证

```bash
python tools/verify_kbs.py --config <ASTRBOT_DATA>/cmd_config.json
```

输出各库 `docs` / `chunks` 统计 + 5 条检索冒烟。也可以用 `--query` 自定义查询。

---

<a id="c-如何让知识库真正参与对话"></a>

## C. 如何让知识库真正参与对话

**建好库不等于会用上。** AstrBot 是否检索、检索哪些库，由配置决定。入口：WebUI → **配置文件** → 选中机器人实际使用的配置 → **AI → 能力 → 知识库**。

### C1. 四个配置项

| 配置项 | 默认值 | 作用 |
| --- | --- | --- |
| `kb_names`（知识库列表） | `[]` | 参与检索的知识库名称列表；**空 = 不检索** |
| `kb_agentic_mode`（Agentic 知识库检索） | `false` | 开启后检索变成 LLM 工具，由模型决定何时查 |
| `kb_fusion_top_k`（融合检索结果数） | `20` | 多库结果融合后的候选数量 |
| `kb_final_top_k`（最终返回结果数） | `5` | 最终交给模型的片段数量 |

### C2. 两个开关都要设（最常见的坑）

- 只设 `kb_names`、不开 Agentic：每轮对话自动检索并注入片段（默认模式）。
- 只开 Agentic、`kb_names` 为空：模型可以调用检索工具，但**工具内部按 `kb_names`（或会话级 kb_ids）确定范围**，为空时只会返回 “No relevant knowledge found.”。
- 正确做法：**勾选 `kb_names` + 打开 `kb_agentic_mode`**（若使用 Agentic），两者缺一不可。

### C3. Agentic 与非 Agentic 的取舍

| 维度 | 普通检索（`kb_agentic_mode=false`） | Agentic 检索（`true`） |
| --- | --- | --- |
| 何时检索 | 每条消息都检索，结果拼进 prompt | 模型自行决定是否/用什么 query 检索 |
| 模型要求 | 不要求工具调用能力 | 需要模型及 API 支持函数调用 |
| prompt 体积 | 每轮固定注入 `kb_final_top_k` 个片段 | 只加工具定义，命中时才带片段 |
| 延迟 | 每次请求都有检索 + 注入开销 | 不查时无额外开销，查时多一轮工具调用 |
| 风格影响 | 容易「每句话都在解释梗」，语气变书面 | 更像自然聊天，但可能该查时不查 |
| 适合 | 客服型、问答型机器人 | 闲聊/角色扮演型机器人（本项目场景） |

实践建议：角色聊天用 Agentic；如果发现模型该查不查，在人格里明确写「遇到网络流行语/黑话/梗时，先调用知识库检索再回答」，或对特定会话用普通检索。

### C4. 会话级 kb_ids 的优先级

WebUI 可以对**单个会话**单独指定知识库（聊天页的会话设置 / 「自定义规则」中的知识库覆盖）：

- 会话级 **kb_ids 优先于全局 `kb_names`**；
- 在界面里清空会话级选择并保存，会移除覆盖，恢复使用配置文件里的知识库；
- 适合「这个群只聊游戏，挂 V吧+弱智吧」「客服会话只挂释义库」这类场景。

### C5. 挂几个库？prompt 体积与延迟的权衡

- 普通检索模式下，每轮都会把 `kb_final_top_k` 个片段拼进 prompt。按每段 200–400 字符估算，5 段约 1000–2000 字符；挂 5 个库还会让召回互相竞争，容易命中不相关片段。
- Agentic 模式成本低一些，但工具返回 `top_k` 段同样会进上下文。
- 建议：**常开 2 个**（网络流行语释义库 + 网梗对话风格库）覆盖「解释梗」和「学语气」；弱智吧、V吧按社群场景加；**地狱笑话库默认不挂**，确有需要再单独会话启用并加安全过滤。

### C6. 推荐配置（等价 JSON）

在 WebUI 保存后的配置形如（这些键位于 AI 能力的知识库分组，不同版本嵌套层级可能不同，**建议直接在 WebUI 改，不必手改文件**）：

```json
{
  "kb_names": ["网络流行语释义库", "网梗对话风格库"],
  "kb_agentic_mode": true,
  "kb_fusion_top_k": 20,
  "kb_final_top_k": 5
}
```

五个库全部启用时：

```json
{
  "kb_names": [
    "网络流行语释义库",
    "网梗对话风格库",
    "弱智吧语料库",
    "V吧黑话库",
    "地狱笑话库"
  ],
  "kb_agentic_mode": true,
  "kb_fusion_top_k": 20,
  "kb_final_top_k": 5
}
```

### C7. 验证是否生效

1. 普通检索模式：问一个语料里明确有的问题，看回答是否用上（可在日志里看到检索相关记录）。
2. Agentic 模式：先要求「**先查询知识库，再回答**：什么是独轮车？」，确认发生工具调用；再试自然提问，观察模型是否主动查。
3. 如果回答仍不带语料：检查配置文件是否保存、会话级是否有覆盖、模型是否支持工具调用、`kb_names` 是否拼写与库名完全一致。

---

## 常见失败速查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 脚本 401 | `--config` 指向错文件 / 时钟偏差 | 核对 `dashboard.jwt_secret`，重开 AstrBot |
| 脚本 403 `Insufficient API key scope` | 用了 `abk_` API Key | 改用本机 JWT（脚本默认）或 WebUI |
| 创建库失败 | embedding provider 不可用 | 在 WebUI 检查提供商可用性与维度 |
| `chunk_count` 不一致 | 孤儿 chunk / 重分块 | `--force` 重建 |
| 检索结果为空 | `kb_names` 为空、库名不一致、维度不符 | 见 [FAQ](FAQ.md#retrieval-miss) |
