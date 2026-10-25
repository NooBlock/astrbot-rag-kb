# 02_meme_style — 网梗对话风格库 💬

中文互联网网梗对话风格语料，供给 AstrBot 知识库「网梗对话风格库」（kb_name=`网梗对话风格库`）。
目标是让检索到的片段带有「用户抛梗 → 回复接梗」的语气，而不是让模型学事实。

## 数据来源

| 项 | 内容 |
| --- | --- |
| 数据集 | `GaryYang123/zh-meme-sft-8k`（HuggingFace Datasets） |
| URL | https://huggingface.co/datasets/GaryYang123/zh-meme-sft-8k |
| 文件 | `train.jsonl`（7377 行）、`validation.jsonl`（868 行），共 8245 组 user/assistant 对话 |
| 许可 | 上游未单独声明，按「见上游 HF 数据集页 / 仅限自用」处理；原始数据留存在 `raw/` |
| 语言 | zh-CN |

原始格式：每行 `{"messages":[{"role":"user","content":...},{"role":"assistant","content":...}]}`。

## 构建方法

1. 读取 train + validation 全部 8245 组对话，取 user / assistant 首轮内容。
2. **清洗过滤**（共剔除约 1017 组，保留 7228 组）：
   - 空串、纯符号/纯表情、控制字符；
   - URL、贴吧/微信/QQ 等联系方式与广告（加微、代购、刷单、优惠券、公众号等）；
   - 与「网梗口语」无关的通用 AI 长回答：≥150 字，或 ≥100 字且含「建议/推荐/首先/其次/总之/1）2）」等书面条列结构；
   - 完全重复的 user+assistant 对。
3. **主题分桶**：按关键词把对话对分到 18 个粗粒度主题（职场打工、校园学习、恋爱情感、家庭亲戚、吃喝美食、购物消费、游戏电竞、追星影视、网络流量、宠物动物、身体健康、生活日常、情绪发疯、运动健身、音影动漫、社交人际、抽象玩梗、数码科技，以及「杂谈其他」），
   桶内每 **4 组**（少量 3/5/6 组）对话合并为 1 条 chunk，使同一 chunk 内语境相近、避免语义稀释。
4. **格式**（与任务约定一致，未改写原文语气，emoji 保留）：

   ```
   对话：
   用户：……
   回复：……

   用户：……
   回复：……
   ```

5. `id` 从 0 自增；全程 UTF-8 无 BOM；chunk 长度控制在 102–588 字符（远小于 1200 上限）。

## 抽样策略

未做抽样：清洗后 7228 组对话**全量使用**，按主题桶顺序打包，得到 **1804 条 chunk**（每条约 4 组对话，平均 223 字符）。
不按长度或热度筛选，避免丢失小众梗。

## 注意事项 / 已知局限

- 源数据自称 meme-sft，但混有约 10% 的通用助手问答（考公、WiFi、书单等），已按长度+句式启发式剔除，仍可能有少量漏网，检索时表现为「书面口气」而非梗味。
- train / validation 两个 split 风格略有差异（validation 通用问答比例更高），未重新划分，`raw/` 保留原文件便于复查。
- 按关键词分桶相对粗放，「杂谈其他」桶内的 chunk 主题一致性弱于其他桶；chunk 头统一以「对话：」开头，不额外加主题标签，避免污染口语样本。
- 语料含互联网口语中的夸张、自嘲、损友互怼等表达，仅作风格参考；其中个别内容可能带有冒犯性，使用时需自行把控。

## 复现（可选）

> `chunks.jsonl` / `manifest.json` 已是最终产物，可直接导入，**普通使用者无需重新构建**。
> 原始抓取数据（`raw/`）因体积与第三方版权原因不随本仓库发布。
> `_download.py` 会把 HuggingFace 原始数据下载到 `corpora/02_meme_style/raw/`。

```powershell
# 在仓库根目录执行；脚本需要 requests / beautifulsoup4 / lxml
python scripts\build\02_meme_style\_download.py      # 下载到 corpora/02_meme_style/raw/
python scripts\build\02_meme_style\_build.py         # 生成产物
python tools\validate_corpus.py corpora\02_meme_style
```
