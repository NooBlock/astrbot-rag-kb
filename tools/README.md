# tools/

AstrBot 知识库的导入、校验与检索冒烟脚本。

| 脚本 | 作用 |
| --- | --- |
| `validate_corpus.py` | 校验 `chunks.jsonl` / `manifest.json` 是否符合规范（JSON、字段、长度、去重、条数一致性） |
| `kb_client.py` | 最小化的 AstrBot 知识库 HTTP 客户端（用 `cmd_config.json` 的 `dashboard.jwt_secret` 本机签发 JWT） |
| `build_kbs.py` | 扫描 `corpora/` 建库并导入，幂等（按内容 sha256 判断是否重建） |
| `verify_kbs.py` | 打印各库统计并跑一组检索冒烟测试 |

```bash
pip install -r tools/requirements.txt
python tools/validate_corpus.py --all corpora
python tools/build_kbs.py --config /path/to/astrbot/data/cmd_config.json
python tools/verify_kbs.py --config /path/to/astrbot/data/cmd_config.json
```

`build_kbs.py` 常用参数：

| 参数 | 说明 |
| --- | --- |
| `--config` | AstrBot 的 `cmd_config.json`（也可用环境变量 `ASTRBOT_CONFIG`） |
| `--root` | 语料根目录，默认仓库下的 `corpora/` |
| `--only` | 只处理指定目录，如 `--only 01_cheer_terms` |
| `--embedding-provider-id` | 新建知识库用的 embedding provider id，默认 `openai_embedding` |
| `--create-only` | 只建库，不导入 |
| `--force` | 忽略内容哈希，删库重建 |

> `cmd_config.json` 含 JWT 密钥，**不要提交到仓库或发给别人**。
