# 网络流行语释义库（01_cheer_terms）

AstrBot 知识库「网络流行语释义库」（emoji 🗣️）的语料产物。每条 chunk 是一个中文网络流行语的
自包含释义片段，可直接用于 embedding 检索。

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `chunks.jsonl` | **必需产物**。1219 行，每行 `{"id": int, "text": "..."}`，UTF-8 无 BOM |
| `manifest.json` | **必需产物**。AstrBot 导入用的知识库元信息 |
| `raw/build_cheer.py` | 可复现的构建脚本（下载 → 解析 → 清洗 → 切片 → 写产物） |
| `README.md` | 本文件 |

原始数据 `data.py` 约 5.2 MB，未随语料保留（按 SPEC 要求，`raw/` 不放大文件）。

## 数据来源

- 仓库：<https://github.com/SCUNLP/Buzzword>（四川大学 SCUNLP，ACL 2025 Main）
- 直接数据文件：<https://raw.githubusercontent.com/SCUNLP/Buzzword/main/data/data.py>
  （构建时大小 5,214,058 字节，格式为 `rawdata = {词条: {...}}` 的 Python 字面量）
- 论文：Chen Huang, Junkai Luo, Xinzuo Wang, Wenqiang Lei, Jiancheng Lv.
  *Can Large Language Models Understand Internet Buzzwords Through User-Generated Content.*
  ACL 2025. <https://arxiv.org/abs/2505.15071>

上游 README 给出的字段含义（本项目只取前三个）：

| 上游字段 | 本项目用途 |
| --- | --- |
| `definition` | 【释义】简洁定义 |
| `examples` | 【例句】例句列表（仅 49 个词条非空） |
| `ground_truth` | 【详解】较详细的背景与用法介绍 |
| `*_KEY` | 不使用：6 个 LLM 生成的释义，上游打分显示存在明显事实错误 |
| `*_score` | 不使用：LLM 互评打分，非语料内容 |

## 许可（重要）

上游仓库 `SCUNLP/Buzzword` **未提供 LICENSE 文件**（GitHub API 的 `license` 字段为空），
该数据是 ACL 2025 论文的配套研究数据集，**未声明开放许可**。

- 本项目按「研究／自用」用途使用，仅作为个人 AstrBot 的知识库，不对外分发数据集本体。
- 若要再分发、商用或公开部署，请先联系原作者取得授权，并在成果中引用上述论文。
- 词条内容为上游作者整理／标注的文本，本项目不额外主张版权。

## 构建方法

1. 下载（如需代理，请配置 `HTTP_PROXY`/`HTTPS_PROXY`） `data/data.py`。
2. 去掉首行注释，从 `rawdata` 后第一个 `{` 起用 `ast.literal_eval` 解析，得到 1183 个词条。
3. 每个词条拼成：

   ```
   【词条】X
   【释义】...
   【例句】...      # 仅上游有例句时出现
   【详解】...
   ```

4. 清洗规则：
   - 去零宽字符（U+200B/200C/200D/FEFF/2060）、控制字符；
   - `\r\n`、全角空格、连续空白压缩为单个空格；
   - 上游把书名写成裸尖括号（如 `<长河浪花集>`、`<赢天下>`），统一规范为 `《长河浪花集》`，
     避免被误判为 HTML 标签；其余尖括号替换为 `‹ ›`；
   - 不截断释义内容，不做人工改写。
5. 切片：单条 ≤ 900 字符则 1 个词条 = 1 个 chunk；超过 900 字符的 28 个长词条
   （多为百科式长详解，最长约 2300 字符）按句末标点（`。！？；…`）拆成 2–4 片，
   每片开头重复 `【词条】X（续）`，续行标注 `【详解】（续）`，各片长度均衡（398–891 字符）。
6. 完全相同的 `text` 只保留一条（构建后无重复）。

复现命令（PowerShell）：

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
& "python" `
  ".\01_cheer_terms\raw\build_cheer.py"
& "python" `
  ".\tools\validate_corpus.py" `
  ".\01_cheer_terms"
```

## 统计

| 指标 | 数值 |
| --- | --- |
| 上游词条数 | 1183（全量使用，**未抽样**） |
| 产物 chunk 数 | 1219（28 个长词条共拆出 36 条续片） |
| text 长度 | min 49 / avg 325 / max 891 字符 |
| 带【例句】的词条 | 49 |
| 完全重复 text | 0 |
| 自检 | `tools/validate_corpus.py` → `[OK] 校验通过` |

## 已知局限

- 释义、详解为上游研究数据集的标注／整理文本，不是逐条人工复核过的词典；个别条目的
  流行时间、出处可能有偏差或已过时。
- 4 个词条原文极短（49–76 字符），chunk 也偏短（如「抱一丝」「撤辣」「茶化」「半场开香槟」），
  仍保持「词条 + 释义 (+ 详解)」的自包含格式。
- 近义词条未合并（如「粉切黑」「粉红切开都是黑」「粉红的切开来里面都是黑的」各自成条），
  检索时可能命中多条近似内容，属预期行为。
- 未收录上游的模型生成释义，因此**不带**额外角度或类比，只有上游的参考释义与介绍。
- 词条以 2010s–2020s 的 B 站／ACG／微博语境为主，2024 年后新梗覆盖有限。

## 复现（可选）

> `chunks.jsonl` / `manifest.json` 已是最终产物，可直接导入，**普通使用者无需重新构建**。
> 原始抓取数据（`raw/`）因体积与第三方版权原因不随本仓库发布。
> 构建脚本会直接从 GitHub 下载 `data/data.py`（约 5.2 MB），无需预先准备 `raw/`。

```powershell
# 在仓库根目录执行；脚本需要 requests / beautifulsoup4 / lxml
python scripts\build\01_cheer_terms\build_cheer.py   # 下载 data.py 并生成产物
python tools\validate_corpus.py corpora\01_cheer_terms
```
