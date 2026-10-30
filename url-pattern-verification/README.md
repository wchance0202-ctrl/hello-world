# 指定pattern 列：URL 正则提取与覆盖核验

## 交接：补齐「正则表达式」列（2026-10-30，替代上一版交接）

用户已把结果汇总成 4 列表（站点名称｜pattern链接｜黑白名单属性｜正则表达式），空白行由其他 AI 补齐。
`handoff/prompt-fill-regex.md` 是新的 prompt，第 1 节定义匹配对象。核心是条目不在入口路径下时，必须先做“专属性证明”。
配套 `handoff/fill-list.xlsx|csv`（由 `scripts/build_fill_list.py handoff` 生成）：
「待补正则」301 行，附空白原因和线索，线索是上一轮在入口页上看到的前缀外同站链接结构；
「已填需复核」73 条，其中范围超界 39 条、验证不通过 10 条、候选 24 条。
上一版 `prompt-remaining.md` 保留作参考。

## 交接：剩余任务（2026-10-30）

`handoff/prompt-remaining.md` 是交给其他 AI 的完整 prompt（正文 `prompt-body.md` + 自动生成的附录 `appendix.md`），
随附 `handoff/remaining-tasks.xlsx|csv|json`（由 `scripts/build_handoff.py handoff` 生成）。
两批剩余 175 个入口、208 条任务，分 T1–T10 十类。第 1 节严格定义了正则的匹配对象（A 正则对象 / B 保留链接 / C 不收录）。
按这个定义复查后发现，第二批有 39 条已交付规则的范围超界：入口边界退化为站点根 `/`，或用变量覆盖了栏目标识
（jazzyear、chinaventure、coalchina）。这些规则已列为 T10 任务，需要重做。

## 第 3 轮（2026-10-26）：全部 268 个入口全量处理 — 最终结果

**最终交付在 `output/round3/`**：结果表 `result-table.xlsx|csv`（152 行原值 + 8 个结果字段，回读检查通过），
规则 `rules.json`，入口账本 `entries.json`，剩余队列 `queue.json`，计数 `summary.json`。
每个入口未被正式规则覆盖的已知目标都列在 `retained/<entry_id>.txt`（共 29,280 条）。

### 一句话结论（2026-10-27 更新）

268 个入口中，**222 个已完成，46 个未完成**：45 个被网站拦截，1 个（Circana Insights）页面上没有可枚举的普通链接。
124 个入口有可用的正则，共 154 条（其中 3 条是你同意按小样本采用的）。

### 结果

| 维度 | 数量 |
|---|---|
| 正式规则（已验证） | **151 条** |
| 用户同意采用（小样本，未经独立留出验证） | 3 条（MSI、wearehuman8、Greenbook GRIT） |
| 合计进入 Pattern 正则列 | 154 条，覆盖 124 个入口 |
| 候选规则 | 9 条（所在入口的链接已保留，不影响完成） |
| 按技能改为保留链接 | 15 个家族（同结构目标只有 3 个，不强凑正则） |
| 验证不通过 | 2 条（规则同时匹配了入口列表页本身） |
| 发现覆盖：完整 | 30 个 |
| 发现覆盖：完整（列表 + sitemap 合并枚举） | 84 个 |
| 发现覆盖：完整（枚举结束，无独立全集对账） | 108 个 |
| 发现覆盖：部分 | 1 个（Circana Insights，Wix 页面没有标准链接） |
| 未验证（访问受限 / 无响应） | 45 个，清单见 `blocked-45.xlsx` |
| 测试对 | 3,168 对；node-re2 1.24.1 与 google-re2 1.1.20251105 逐对一致 |

### 你做出的决定（2026-10-27）

- 接受部分列表链接跳到家族外页面：Contentsquare、Amplitude、Branch、HubSpot website（已转正）；
  WIPO PATENTSCOPE 也已同意，但它还缺独立留出样本，所以仍是候选。
- 6 个缺独立验证样本的入口按现有证据采用：MSI、wearehuman8、Greenbook GRIT 按“采用”计入；
  NRF 两个和 Landor 在修正尾斜杠判定后拿到了独立样本，已正常通过验证。
- 45 个被拦截的入口：清单已发给你，等你决定采用哪种办法（自己用浏览器保存页面、连接你的电脑、或用订阅账号）。

### 未完成的 46 个入口

1. **45 个被站点拦截，没有绕过**：Cloudflare 验证页 30 个、Akamai 拒绝访问 6 个、连接超时 6 个（McKinsey、Adobe）、
   Vercel 429 2 个、Meta 400 1 个。这些站点的 sitemap 同样被拦截；用浏览器重试、读取存档，都被自动模式拦截，没有再尝试。
2. **Circana Insights**：Wix 页面，内容没有使用普通链接，也没有独立的 sitemap。

### 本轮补充解决的问题

- **尾斜杠**：只有当规则自己的样本证明两种形式会互相跳转时，才把带不带尾斜杠视为同一页面；
  否则视为不同类型的页面（例如 GWI 的 `/reports/{slug}/` 是指南页，不是报告）。
- **sitemap 中的页内锚点**（如 IAB 的 `#new_tab`）不算独立页面，不再计为漏配。
- **Pew Research sitemap**：子文件地址里的 `&amp;` 没有还原，导致采集空转；修正后完整遍历 5,810 个文件，
  其中被限流的 405 个放慢后重试成功 404 个，剩下 1 个是确实不存在的文件。
- **YouGov**：页面在接口还剩最后一批时就隐藏了“加载更多”按钮（economy 少 1 条，consumer 少 57 条）。
  用页面自身的只读接口取后续 offset 补齐，58 条全部落地核验 200，合计与接口总数一致（1,016 / 2,717）。
- **Forrester**：页面自身的 More posts 枚举到 1,221 篇，全部在 WP REST 公开文章 1,222 篇内，剩下的 1 篇已定位；
  分类计数 1,287 是 WordPress 内部计数，不作为对账总数。
- **13 个 sitemap 被截断的站点**：完整遍历全部子文件，只保留入口前缀下的 URL；其中 12 个已遍历完。
- 留出样本来源补充了“同站其他页面”“详情页链接”“归纳前拆分列表”“v2 扩展前拆分漏配样本”四种；
  sitemap 中落地失败（404/5xx）的样本不作为正例，只看页面状态，不看规则匹配结果。

### 方法（第 3 轮）

- `scripts/probe_round1.py`：全部入口静态抓取与翻页，同站串行，单入口先跑 300 页，
  BIS publications 与 Semrush blog 续跑到队列清空（510 / 486 页）
- `scripts/collect_sitemaps.py`：109 个站点的 robots/sitemap，共 261 万个 URL。13 个站点达到上限被截断，
  再用 `--prefix-filter` 完整遍历所有子文件、只保留入口前缀下的 URL；只有 pewresearch.org 仍未遍历完（`sitemaps/_summary.json`）
- `scripts/render_batch.py` + `render_probe.js`：91 个静态内容不足的入口用浏览器渲染并点击“加载更多”。
  浏览器以默认 HeadlessChrome 身份访问，不伪装 UA；第 2 轮的渲染曾经伪装过普通 Chrome UA，本轮已改正。
  渲染只用于能正常访问的站点
- `scripts/analyze_r3.py`：
  - `families`：以入口路径前缀作为栏目边界，按结构签名分组，同结构 ≥3 个才算一个家族；
  - `freeze`：先打开归纳样本确认落地，再冻结标签、留出样本和反例（带 sha256）。
    留出来源依次取 sitemap、后续分页、其他入口页面、详情页链接中第一个非空的；
  - `coverage`：用规则匹配列表全部成员和 sitemap 全部同结构 URL；
  - `revise`：对漏配了真实成员、且没有误配的规则，按漏配样本扩展字符集，v1 留出转回归，重新抽取留出（62 条规则）
- `scripts/apply_round3.py`：汇总；`scripts/run_round3.sh`：完整重跑流程
- 正式准入：两套引擎机械门通过且逐对一致、覆盖检查无漏配、归纳样本没有跳到其他页面、
  不匹配家族结构之外的 sitemap URL。留出样本量小（每条 ≤6 正），不外推总体可靠性
- 已压缩的数据：`probe/edges.jsonl.gz`、`detail-links.jsonl.gz`、`sitemaps/*.txt.gz`（`analyze_r3.py` 可以直接读取）

---

## 第 2 轮（2026-10-26，网络已放开）：优先级 1 续跑

本轮输出都在 `output/round2/`，第 1 轮文件未改动。结果表：`output/round2/result-table.xlsx|csv`；
规则：`output/round2/rules.json`；续跑队列：`output/round2/queue.json`；汇总计数：`output/round2/summary.json`。

### 结论

- **正式规则 0 条，候选 4 条。** 两条 Optimizely 规则在两套 RE2 上都通过了机械门，
  但用规则去匹配 sitemap 全部已知成员时发现漏配（真实存在大写字母 slug，如 `…/articles/AI-experimentation`，
  以及末尾带连字符的 slug），因此降级为候选。
- **连通性：** 代理已不再拦截。110 个 host 中 93 个返回 200；11 个站点自身返回 403（Cloudflare/Akamai 挑战页），
  1 个 429（Vercel 检查点），1 个 400；4 个超时，重试后 2 个恢复（CIM、Landor），2 个 HTTP/2 流被重置（McKinsey、Adobe）。
  证据：`output/round2/connectivity.jsonl`、`connectivity-retries.jsonl`。
- **优先级 1 的 45 项：** 39 项完成，6 项受阻（Gartner 5 项被挑战页拦截；Numerator 1 项需要 POST），另新增 8 项续跑。

| 项 | 结果 |
|---|---|
| K1 Forrester B2B Research | **根因已查清。** `/page/N/` 的静态正文不随页码变化，真实分页是 More posts 按钮调用的 `POST admin-ajax.php action=loadposts`（`data-pages=62`）。成员集合通过 WP REST 取得 **1,222 篇**（X-WP-Total，与 62 页×20 条吻合），首页 16 篇全部在内。详情路径是全站共享的 `/blogs/{slug}/`：抽查的 6 篇成员页都带 b2b-research 分类标记，4 篇其他分类同结构页都没有。已生成 28 块精确集合快照，两套 RE2 上有限集合相等成立（1,222 个成员各被一块命中，27 个反例都未命中）。缺口：分类计数 1,287 与公开文章数差 65 篇，原因未查明 |
| K2 Numerator | 总数 606 与前轮一致；前轮未知的 `type` 参数已查清：`filter`=首次加载/筛选，`loadmore`=加载更多。REST 有 640 条，与列表差 34 条未解释。**列表 POST 与 REST 剩余页没有执行**（被本会话的权限分类器拦截） |
| K3 Contentsquare | 本轮静态 HTML 就够用。32 页全部取得，页码连续，没有重复页；共 277 个唯一详情，已逐个打开：274 篇正常，3 篇跳到非文章页。候选规则 `R2-CS-BLOG-DETAIL` 机械门通过，sitemap 中 131 篇全部匹配。**需要你决定**：这 3 个已失效的列表链接被规则匹配，是否可以接受 |
| K4 YouGov | 已证实。Load more 调用的是只读 GET `public-content/content`（limit=35）。economy 已枚举完：接口 1,016 条，页面取得 1,015 个链接。consumer 取得约 1,575/2,717 条，从 offset 1575 续跑。reports 取得 456/460 条。详情都落在全站共享路径，只能保留链接或做快照。`/reports/{id}-{slug}` 列为下一轮候选 |
| K5 跳转样本 | WIPO：181 个子链接中 10 个跳转（多数是 302 补 `/index`，另有改名），1 个 404。Mintel：`/insights/consumer-research/global-predictions/` 301 跳到 `/trend-predictions/`，已证实。Optimizely：16 个详情都是 308 跳到去掉尾斜杠的地址。Gartner：被挑战页拦截，无法复核 |
| 前轮 403 的 6 个入口 | DPAA、Greenbook 3 个、CB Insights 2 个本轮都返回 200，正文是真实栏目页，不是挑战页 |

### 需要你决定或放行

1. **自动模式拦截了两类请求**：Forrester/Numerator 的 `admin-ajax.php` 只读 POST（列表接口），以及 Numerator WP REST 的批量 GET。
   如果允许，请在权限设置里放行，或直接回复确认；对应队列项是 `S1-R50-E3-R2a` 和 `S1-R42-E1-R2a`。
2. **Contentsquare 规则的范围**：3 个已失效列表链接被匹配是否可以接受？接受的话，`R2-CS-BLOG-DETAIL` 可以升为正式。
3. **Optimizely 的 `/thank-you` 表单完成页**是否属于 guides 栏目？v3 写法已经给出（见 `rules.json`），需要另取独立样本验证。
4. **Gartner** 被站点 Cloudflare 挑战页拦截，本轮没有绕过；需要授权的访问方式，或改由人工浏览器核验。

### 方法与文件（第 2 轮）

- `scripts/connectivity_check.py`：按 host 测连通性，区分代理拒绝、网络错误和站点响应
- `scripts/probe_round1.py`：静态首轮与分页（与第 1 轮相同，支持断点续跑）→ `output/round2/probe/`（`edges.jsonl.gz` 已压缩）
- `scripts/redirect_check.py`：逐跳记录跳转 → `k5-redirects.jsonl`、`tests/identity-checks.jsonl`
- `scripts/render_probe.js`：Playwright 渲染，用 `--selector` 点击加载更多，用 `--hide` 以 CSS 隐藏 Cookie 弹层（不点同意），用 `--api` 记录接口总数 → `render/`
- `scripts/freeze_samples_r2.py`、`freeze_samples_r2_v2.py`：先冻结目标、标签和独立样本（带 sha256），再做身份核验
- `scripts/build_tests_r2.py`：组装 `validate_patterns.mjs` 格式的测试；精确快照按“有限集合相等”检查
- `scripts/apply_round2.py`：离线汇总，生成第 2 轮的 entries/rules/queue/结果表；回读检查：`scripts/readback_check.py … output/round2`
- 引擎：node-re2 1.24.1（技能自带 `validate_patterns.mjs`）和 google-re2 1.1.20251105，所有测试对两者结果一致
- 样本隔离：归纳正例取自列表卡片，留出正例取自 sitemap 中不在列表里的成员（固定种子抽样），反例是同站真实存在的近邻页面。
  Optimizely articles v1 留出集漏配 `…website--app`，于是改规则、把 v1 留出集转入回归，再用新种子重新抽取留出集
- 本轮对 268 个入口的覆盖：完整 1 个（YouGov economy，限本次筛选条件）、部分 42 个、未验证 225 个；
  链接可打开 128 个、访问受限 16 个、待核验 124 个（未单独请求的入口只有同 host 首入口的结果，记为待核验）

---

## 第 1 轮（2026-10-26，网络被拦截）

### 结论先行

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
