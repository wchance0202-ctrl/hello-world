# 指定pattern 列：URL 正则提取与覆盖核验（2026-10-26 本轮）

## 结论先行

本轮**没有产生任何已验证规则或新候选**。原因是外部阻塞，不是工作被跳过：

1. **目标站全部不可达。** 本会话所在云环境的网络策略是“trusted network access”（只放行包管理器等）。
   对全部 109 个入口 host 及 YouGov 脚本域 `d18w79e3uiqk2z.cloudfront.net` 各尝试一次，
   110/110 在代理 CONNECT 阶段被拒（`CONNECT tunnel failed, response 403`）。请求没有到达任何目标站，
   所以这**不是站点返回的 HTTP 403**，也不能说明页面可用或不可用。WebFetch 同样无法解析目标域名。
   证据：`output/access-attempts.jsonl`。
2. **前轮检查点无法恢复。** 本轮只收到 `extract-url-patterns` 技能包，没有收到证据 ZIP
   （entries/candidates/visits/re2-tests 等），也没有收到附件「已粘贴的文本.txt」。
   前轮的 255 条候选、5,633 个分页访问、Numerator 606 条列表等**只作为历史记录写进备注和续跑队列**，
   不复用，也不当作本轮结论。

## 已完成、可以使用的部分

| 项目 | 状态 | 文件 |
|---|---|---|
| 输入解析与分流 | 完成。337 个非空项 → 268 个带路径入口（268 个唯一 URL）、24 个纯 host 免提、45 个“/”占位跳过，与前轮检查点一致 | `input/classified.json`、`output/entries.json` |
| 152 行重建 | 完成，但属于**重建**：内联粘贴丢了引号，按“连续同注册域为一格、每个 / 为一行”分组，恰好得到 152 行（107 个 URL 单元格 + 45 个占位行），而且你举例的 `S1-R50-E3` 正好落在 Forrester B2B Research 入口。仍需拿原始文件核对一次 | `output/entries.json`（`row_boundary: reconstructed`） |
| 结果表副本 | 完成。保留 152 行原值，在指定列后加 8 个结果字段；占位行 8 字段为空；纯 host 行只写“host免提”；同格多入口按 E 序号分别映射 | `output/result-table.xlsx`、`output/result-table.csv` |
| 回读检查 | 通过：原值逐行还原输入、行数 152、占位/host 规则、每个入口都出现在保留链接/来源映射/发现覆盖中、最长单元格 2,144 字符（无截断） | `output/readback.json`、`scripts/readback_check.py` |
| RE2 引擎 | 就绪：google-re2 1.1.20251105（Python）与 node-re2 1.24.1（技能自带 `validate_patterns.mjs`）。两者在技能自带的 7 对**合成**样例上结果一致。这只证明引擎能跑，**不是任何网站规则的测试** | `output/engine-check/` |
| 续跑队列 | 完成。1,647 项：每个入口 6 步（访问/发现/分页/动态/家族/验证），另加前轮已知问题 K1–K5；6 个前轮 403 入口和已知问题入口为优先级 1 | `output/queue.json` |
| 放行清单 | 完成。109 个入口 host + 1 个已知依赖域 | `output/hosts-allowlist.txt` |
| 续跑脚本 | 已写好并在本地夹具站上测试：逐跳记录跳转、页面身份（标题/H1/canonical/正文哈希/疑似挑战页）、链接区域（nav/header/footer/main）、普通锚点不计页、分页链接推进、**分页主链接集合与前页相同时标记重复页**（对应 Forrester 第 2 页问题）、断点续跑不重复请求、未完成分页跨次保留 | `scripts/probe_round1.py`、`scripts/run_re2_py.py` |

## 只是候选、不能当成品的部分

- 本轮**候选为 0**，`output/rules.json` 中 `formal` 与 `candidates` 均为空。
- 结果表里“保留链接”列目前只有**入口本身**（入口保留形式）。按技能，这不是下级覆盖规则，不能覆盖分页、详情或跳转目标。
- 前轮的 255 条候选、16 条 Forrester 有限集合、606 条 Numerator 列表都不在本轮文件中，不能当作可用结果。

## 进度（分开报告，不合成百分比）

| 维度 | 本轮 | 说明 |
|---|---|---|
| 入口 | 268 个：完整 0、部分 0、未验证 268 | 本轮 0 个目标站请求成功；前轮“262 部分 / 6 未验证”只是历史 |
| 规则 | 正式 0、候选 0、测试对 0 | 前轮 7,383 个结构回归对是历史数据，且只是结构测试 |
| 目录页面 | 本轮 0 | 前轮 3,687 个不同 HTTP 目标的明细未随附 |
| 详情/文件/跳转 | 本轮 0 | 包括 Numerator 606 条详情、8 个跳转样本，都待核验 |
| 阻塞 | 2 项 | 网络策略；前轮证据包与原始附件未上传 |

## 需要你做的事

1. **放开网络。** 在会话标题栏的云环境菜单 → Edit → Network access 中，选择完整访问；
   或在 Limited 级别的 Allowed domains 里加入 `output/hosts-allowlist.txt` 中的域名（保持 Allow package managers 勾选）。
   浏览器渲染类入口（Contentsquare、YouGov 等）还会加载未知的第三方脚本和接口域，建议直接用完整访问。
   说明：https://code.claude.com/docs/en/cloud-environments#network-access
2. **上传前轮证据 ZIP**（不上传也能从头跑，但会重复约 5,600 次请求，而且丢失前轮的跳转样本与 Numerator 接口参数，比如 `type` 的取值）。
3. **上传原始「已粘贴的文本.txt」或原表**，用来确认 152 行边界重建无误。

以上任一项就绪后，按下面的顺序续跑：

```sh
cd url-pattern-verification
python3 -I scripts/probe_round1.py output/entries.json output/run --max-pages 20 --delay 1
# 结束后按 output/queue.json 的优先级 1 项处理 K1–K5 和 6 个前轮 403 入口，
# 再按技能 3–4 步归纳规则、冻结独立样本，用两套 RE2 实测：
node <skill>/scripts/validate_patterns.mjs tests.json > node-re2.json   # engine_module 指向 node-re2
python3 -I scripts/run_re2_py.py tests.json > google-re2.json
python3 -I scripts/build_ledger.py input/原始输入_内联粘贴.txt input/classified.json output   # 重建结果表
python3 -I scripts/readback_check.py input/原始输入_内联粘贴.txt output
```

续跑脚本的已知限制：只做静态 HTML；动态入口（K2 Numerator 接口、K3 Contentsquare、K4 YouGov）要用预装的 Playwright 另行处理。
重复页检测只在同一次运行内比较。同站多个入口共享“已访问”集合，因此 Forrester 第 2 页若已作为第 1 页的分页被访问，
就不会在 E4 下重复请求，记录挂在 E3 下。

## 文件索引

- `input/原始输入_内联粘贴.txt`：本轮实际使用的输入（来自对话内联粘贴）
- `output/result-table.xlsx|csv`：结果表副本（原值 + 8 个字段）
- `output/entries.json`：337 个项的稳定 ID（`S1-R{行}-E{格内序号}`）、分流、行重建标记、前轮状态与已知问题
- `output/rules.json`：机器可读规则文件（本轮 formal/candidates 为空，附引擎信息）
- `output/queue.json`：续跑队列
- `output/access-attempts.jsonl`：本轮 110 次访问尝试与拒绝记录
- `output/hosts-allowlist.txt`：需放行的域名
- `output/engine-check/`：两套 RE2 在合成样例上的执行记录
- `scripts/`：ledger 构建、续跑探测、google-re2 执行、回读检查
