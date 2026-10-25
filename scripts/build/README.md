# scripts/build/

构建期参考脚本，按语料目录分组：

| 目录 | 脚本 | 说明 |
| --- | --- | --- |
| `01_cheer_terms/` | `build_cheer.py` | 下载 SCUNLP/Buzzword 的 `data.py` 并解析、清洗、切片 |
| `02_meme_style/` | `_download.py` + `_build.py` | 从 HuggingFace 下载 zh-meme-sft-8k 并分桶合块 |
| `03_ruozhiba/` | `_download.py` + `_build.py` | 从 HuggingFace 下载弱智吧两个数据集并清洗抽样 |
| `04_vbar/` | `build_vbar.py` | 从人工抓取的知乎/萌娘百科文本抽取词条 |
| `05_hell/` | `fetch_jandan*.py` + `build_hell.py` | 抓取辅助 + 地狱笑话筛选与格式化 |

注意：

- 这些脚本**不是**导入知识库所必需的；仓库里的 `chunks.jsonl` 已是最终产物。
- 原始数据 `raw/` 不随仓库发布，脚本默认读取 `corpora/<语料名>/raw/`，请先按需下载或自行抓取。
- 依赖：`requests`、`beautifulsoup4`（部分脚本）、`lxml`；仅在重建语料时需要。
- 抓取网页请自行遵守目标站点的 robots/版权规定。
