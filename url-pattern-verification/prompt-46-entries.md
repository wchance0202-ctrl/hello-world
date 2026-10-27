# 任务：为 46 个网站栏目入口提取 URL 收录正则并核验覆盖

> 使用说明：把下面整份内容交给执行任务的 AI。它需要一个能**以正常身份打开网页**的环境，例如公司内网的浏览器，或已获授权的账号。
> 能运行 Python 更好（第 8 步要实际运行 RE2）；如果不能运行代码，也可以按第 8 步的“无代码方式”执行，但交付时必须说明。

---

## 0. 背景与目标

我们在维护一张表，表里的「指定pattern」列每个单元格是一个或多个**栏目入口 URL**（例如某网站的博客首页、报告列表页）。
对每个入口，需要交付：

1. **Pattern 正则**：能匹配该栏目下属页面（列表分页、详情页、必要的文件、实际跳转目标）的正则表达式。
   正则必须**兼容 RE2**，并且要匹配**完整 URL**。
2. **保留链接**：正则无法安全覆盖、但确实属于该栏目的已知 URL，原样列出。
3. **核验证据**：每条正则都要经过真实样本测试；每个入口要说明栏目内容找全了没有。

其余 222 个入口已经处理完毕。下面这 46 个入口当时打不开（被站点防护拦截、超时，或页面没有普通链接），交给你处理。

**最重要的原则：只交付有证据的结论。** 看不到的就写“未验证”，不猜测、不编造、不把少量样本的结果说成全部。

---

## 1. 访问边界（必须遵守）

- 只做**只读访问**：打开页面、翻页、点击“加载更多/More/Load more”这类展示按钮。
  不提交表单，不注册、订阅、下载需要留资的内容，也不点赞、收藏或联系销售。
- **不绕过任何访问限制**：遇到验证码、登录墙、付费墙、“Access Denied”或“Just a moment...”，
  人工通过就记录为“需人工通过”；过不了就记为**访问受限**，然后跳过。
  不要使用伪装浏览器指纹、代理轮换、打码服务、抓取网页存档副本等绕过手段。
- 如果公司已订阅某站点（如 Crunchbase、PitchBook、Dealroom），可以用**有权使用的账号**登录访问。
  但交付物里不得出现 Cookie、Token、账号或任何认证信息。
- 控制速度：同一站点同一时间只开一个页面，相邻请求至少间隔 1–2 秒；连续出现 429/403 时立即停止该站点并记录。
- 交付的 URL 一律保留**原始形式**：不改大小写，不删 query，不重排参数，不额外解码或编码。

---

## 2. 待处理的 46 个入口

`entry_id` 是全局唯一键，交付时必须原样使用。`原表行` 是结果表中的行号，同一行可能有多个入口（E1、E2……）。

| # | entry_id | 原表行 | 入口 URL | 当时的情况 |
|---|---|---|---|---|
| 1 | S1-R3-E1 | 3 | https://www.bls.gov/cex/ | Akamai 拒绝访问（403） |
| 2 | S1-R3-E2 | 3 | https://www.bls.gov/news.release/cesan.htm | Akamai 拒绝访问（403） |
| 3 | S1-R34-E1 | 34 | https://www.circana.com/insights | 能打开，但是 Wix 页面，没有普通 `<a href>` 链接，也没有独立 sitemap |
| 4 | S1-R46-E1 | 46 | https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights | 连接超时 |
| 5 | S1-R46-E2 | 46 | https://www.mckinsey.com/capabilities/strategy-and-corporate-finance/our-insights | 连接超时 |
| 6 | S1-R46-E3 | 46 | https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights/marketing-organization-and-operations | 连接超时 |
| 7 | S1-R47-E1 | 47 | https://www.bcg.com/capabilities/marketing-sales/insights | Akamai 拒绝访问（403） |
| 8 | S1-R47-E2 | 47 | https://www.bcg.com/capabilities/customer-insights/insights | Akamai 拒绝访问（403） |
| 9 | S1-R47-E3 | 47 | https://www.bcg.com/industries/retail/insights | Akamai 拒绝访问（403） |
| 10 | S1-R47-E4 | 47 | https://www.bcg.com/industries/consumer-products-industry/insights | Akamai 拒绝访问（403） |
| 11 | S1-R51-E1 | 51 | https://www.gartner.com/en/marketing/insights | Cloudflare 验证页 |
| 12 | S1-R51-E2 | 51 | https://www.gartner.com/en/sales/insights | Cloudflare 验证页 |
| 13 | S1-R51-E3 | 51 | https://www.gartner.com/en/customer-service-support/insights | Cloudflare 验证页 |
| 14 | S1-R51-E4 | 51 | https://www.gartner.com/en/finance/insights | Cloudflare 验证页 |
| 15 | S1-R51-E5 | 51 | https://www.gartner.com/en/supply-chain | Cloudflare 验证页 |
| 16 | S1-R51-E6 | 51 | https://www.gartner.com/en/insights/finance | Cloudflare 验证页 |
| 17 | S1-R63-E1 | 63 | https://transparency.meta.com/policies/ | 站点返回 400 |
| 18 | S1-R81-E1 | 81 | https://www.campaignlive.com/news | Cloudflare 验证页 |
| 19 | S1-R81-E2 | 81 | https://www.campaignlive.com/in-depth | Cloudflare 验证页 |
| 20 | S1-R93-E1 | 93 | https://lbbonline.com/work | Cloudflare 验证页 |
| 21 | S1-R93-E2 | 93 | https://lbbonline.com/news | Cloudflare 验证页 |
| 22 | S1-R93-E3 | 93 | https://lbbonline.com/reels | Cloudflare 验证页 |
| 23 | S1-R101-E1 | 101 | https://searchengineland.com/library/guide | Cloudflare 验证页 |
| 24 | S1-R101-E2 | 101 | https://searchengineland.com/guide | Cloudflare 验证页 |
| 25 | S1-R101-E3 | 101 | https://searchengineland.com/library/guide/content-marketing-guide | Cloudflare 验证页 |
| 26 | S1-R101-E4 | 101 | https://searchengineland.com/library/guide/ppc-guide | Cloudflare 验证页 |
| 27 | S1-R101-E5 | 101 | https://searchengineland.com/library/guide/seo-guide | Cloudflare 验证页 |
| 28 | S1-R110-E1 | 110 | https://www.vml.com/expertise/intelligence | Cloudflare 验证页 |
| 29 | S1-R110-E2 | 110 | https://www.vml.com/insights | Cloudflare 验证页 |
| 30 | S1-R112-E1 | 112 | https://www.adjust.com/resources/ | Vercel 安全检查（429） |
| 31 | S1-R112-E2 | 112 | https://www.adjust.com/blog/ | Vercel 安全检查（429） |
| 32 | S1-R143-E1 | 143 | https://business.adobe.com/resources/reports.html | 连接超时 |
| 33 | S1-R143-E2 | 143 | https://business.adobe.com/resources/digital-trends-research-center.html | 连接超时 |
| 34 | S1-R143-E3 | 143 | https://business.adobe.com/resources/adobe-digital-insights.html | 连接超时 |
| 35 | S1-R144-E1 | 144 | https://www.crunchbase.com/discover/organization.companies | Cloudflare 验证页 |
| 36 | S1-R145-E1 | 145 | https://pitchbook.com/news | Cloudflare 验证页 |
| 37 | S1-R152-E2 | 152 | https://dealroom.co/reports | Cloudflare 验证页 |
| 38 | S1-R152-E3 | 152 | https://dealroom.co/resources | Cloudflare 验证页 |
| 39 | S1-R152-E4 | 152 | https://dealroom.co/news/ | Cloudflare 验证页 |
| 40 | S1-R152-E5 | 152 | https://dealroom.co/companies/ | Cloudflare 验证页 |
| 41 | S1-R152-E6 | 152 | https://dealroom.co/investors/ | Cloudflare 验证页 |
| 42 | S1-R152-E7 | 152 | https://dealroom.co/market-maps/ | Cloudflare 验证页 |
| 43 | S1-R152-E8 | 152 | https://dealroom.co/power-law-outcomes/ | Cloudflare 验证页 |
| 44 | S1-R152-E9 | 152 | https://dealroom.co/talent/founder-mafias/ | Cloudflare 验证页 |
| 45 | S1-R152-E10 | 152 | https://dealroom.co/tech-macro-economics/ | Cloudflare 验证页 |
| 46 | S1-R152-E11 | 152 | https://dealroom.co/vc-investment-dashboard/ | Cloudflare 验证页 |

**已知线索**（来自更早一轮的人工记录，需要复核，不能直接当结论）：

- Gartner：部分 `/insights/` 列表里的链接会跳到 `/research/`、`/articles/` 等路径。按实际跳转链处理：跳转前和跳转后的 URL 都要登记。
- Crunchbase `discover`、Dealroom `companies/`、`investors/` 很可能是数据库应用页，需要登录，内容是数据记录而不是文章。
  如果没有授权账号，就只保留入口本身，结果类型写“链接保留”，覆盖状态写“未验证（需登录）”。
- 同一网站的多个入口（如 BCG 4 个、Gartner 6 个、Dealroom 10 个）请**串行**处理，并共享“已访问”记录，避免重复请求。

---

## 3. 匹配契约（所有正则共同遵守）

- 匹配对象是**完整 URL**，包括协议、主机、路径和 query；不含 `#` 后的普通锚点。
- 每条正则都以 `^` 开头、以 `$` 结尾，**区分大小写**，不对 URL 做规范化。
- 只能使用 RE2 支持的语法：**不能用**前瞻/后顾（`(?=` `(?!` `(?<=` `(?<!`）、反向引用（`\1`）或占有量词。
- 字面量必须转义，如 `.` → `\.`、`-` → `\-`、`?` → `\?`。
- **禁止**用 `.*`、`.+`、`(?:[?#].*)?` 或无限层级的路径来凑覆盖率。每个变量段都必须有依据：字符集、层级和参数名都要能在样本里找到。
- 不要无依据地放宽协议、`www`、尾斜杠、大小写或参数顺序。

---

## 4. 处理流程（逐个入口执行，每一步都要留记录）

### 第 1 步：打开入口，记录身份

- 记录：请求 URL、每一跳跳转（状态码 + Location）、最终 URL、最终状态码、页面标题、H1、正文是否正常。
- 判断页面类型：
  - 正常页；
  - 挑战页或登录页（如 “Just a moment...”、“Access Denied”、验证码）；
  - 软 404：状态是 200，但内容是 “Page not found”；
  - 空壳：只有页头页脚，主体靠脚本加载。
- 打不开就停在这一步：链接状态写“访问受限”，并附上原因和观察时间。

### 第 2 步：确定栏目边界（入口前缀）

把**入口路径的前缀**作为栏目边界，只有前缀之内的页面才可能被归纳为该栏目的正则：

- 入口以 `/` 结尾（如 `/news/`）：前缀就是 `/news/`。
- 入口不带斜杠、没有扩展名（如 `/en/marketing/insights`）：前缀是 `/en/marketing/insights/`。
- 入口是文件形式（如 `/resources/reports.html`）：如果页面链接到 3 个以上 `/resources/reports/...` 下的地址，前缀取 `/resources/reports/`，否则取上级目录 `/resources/`。
- SharePoint 形式（如 `/en/ITU-R/Pages/default.aspx`）：前缀是 `/en/ITU-R/`。

前缀之外的同站链接（例如多个栏目共用的 `/articles/{id}`）**一律不泛化**，只能保留链接。原因：这类 URL 本身不包含栏目信息，正则无法区分它属于哪个栏目。

### 第 3 步：枚举栏目内容（找全）

1. 只看页面**主体区域**的链接，排除页头、导航、页脚和侧栏。
   例外：有些网站把栏目条目列表放在 `<nav>` 里。如果主体区域里前缀内的链接不到 3 个，就改看 nav/header 里**前缀内**的链接，并在记录里注明。
2. **翻页与加载更多**：
   - 识别分页链接（`/page/N/`、`?page=N`、`?p=N`、`?offset=N` 等），一直翻到最后一页。只跟随入口前缀内的分页，不要翻到其他语言或其他栏目。
   - 有“Load more / More posts / Show more”按钮的，反复点击，直到按钮消失，或者连续 3 次没有新内容。
   - **核对页码是否真的生效**：比较第 1 页和第 2 页的主体链接集合，完全相同就说明服务器忽略了页码。要去找真实的加载方式，比如按钮背后的接口。
3. **对账总数**：如果页面上显示了总数（如 “606 Results”），或者它自己的接口返回了 `total`/`hits`，要和实际取得的条目数对比。差额必须找到原因，原因找不到就如实写“差 N 条未解释”。
4. 每条链接都要记录：`entry_id`、`parent_url`（在哪一页发现的）、`raw_href`（原始写法）、`resolved_url`（解析后的完整地址）、所在区域、链接文字和关系类型。
   关系类型分为：分页、详情、子栏目、文件、导航、推荐、站外、技术链接。
5. 普通页内锚点（`#section`、`#new_tab`）不算独立页面；Hash 路由（`#!/…`、`#/…`）要保留。

### 第 4 步：收集独立来源（用于验证，必须与列表页分开）

按以下顺序收集，供第 6 步抽取“留出样本”：

1. **sitemap**：先读 `robots.txt` 中的 `Sitemap:` 行；没有的话，依次尝试 `/sitemap.xml`、`/sitemap_index.xml`、`/sitemap-index.xml`。
   - sitemap 索引要**递归展开**，`.gz` 文件要解压；
   - `<loc>` 里的 `&amp;` 要先还原成 `&` 再请求（否则会反复请求到同一个索引）；
   - 记录读了多少个文件、哪些失败。失败的文件要放慢速度重试；
   - 如果 sitemap 太大，可以只保留入口前缀下的 URL，但**所有子文件都要读完**，才能说“已完整遍历”；
   - 去掉 URL 中的普通锚点。
2. **后续分页**：如果列表只有入口首页，就没有这个来源。
3. **同站其他页面上出现的链接**：其他入口的页面、详情页上的“相关文章”等。

### 第 5 步：按 URL 结构分组（找“家族”）

对每个入口前缀内的链接（去掉入口页本身和分页页），按**结构签名**分组：

- 前缀之后有几段路径；
- 是否带尾斜杠；
- query 的参数名集合；
- 文件扩展名。

规则：

- 同一签名下 **≥ 4 个**不同 URL，才算一个可以泛化的家族。
- 只有 **1–3 个**同结构目标的，**不要强凑正则**，直接作为保留链接。
- 在同一路径位置上，所有样本取值都相同的（如 `page`、`2026`），按字面量处理；取值不同的才是变量。
  注意：“2026”只在当年的样本里出现时，不能凭此推断它是变量。要等样本里出现其他年份，才能改为变量。

### 第 6 步：先冻结样本，再归纳（防止“看着答案出题”）

在写正则**之前**，先把以下三组样本定下来并保存。保存时附上文件的 sha256 和时间：

- **归纳集**（用来写正则）：
  - 有 sitemap 可作留出时：列表页上取得的全部成员；
  - 没有 sitemap 时：只用入口首页上的成员，后续分页留作验证。
- **留出正例**：每个家族 1–6 个，**不能出现在归纳集里**，用固定随机种子抽取。来源按优先级：
  1. sitemap 中结构相同、但列表里没有的 URL；
  2. 后续分页上的成员；
  3. 同站其他页面上出现的同结构链接；
  4. 以上都没有时，在归纳**之前**按固定种子从列表成员中随机拆出约 1/4（至少 1 个、最多 6 个）作为留出。成员不足 4 个时不能拆分。
- **留出反例**：至少 3 个，必须是同站**真实存在**的 URL。优先选：
  - 入口页本身和分页页；
  - 前缀之外、路径层级相同的同站页面；
  - 前缀内但属于其他家族的成员。

**尾斜杠的判定**：带不带尾斜杠，只有在**归纳样本自己的跳转**证明两种形式指向同一页面时，才算同一家族。
例如列表链接带斜杠，打开后 308 跳到不带斜杠的地址，这时两种形式都要覆盖，正则末尾写 `/?`。
否则，斜杠不同就是不同类型的页面。

**冻结之后，绝对不能为了让测试通过而修改任何样本的期望标签。**

### 第 7 步：写正则

对每个家族：

- 写法：`^` + 转义后的协议与主机 + 转义后的前缀 + 各段（字面量段转义，变量段用字符集） + 尾斜杠处理 + query + `$`。
- 变量段的字符集只取**归纳集里实际出现过的字符类别**：
  - 全是数字：`[0-9]+`；
  - 否则按出现情况组合，例如 `[a-z0-9-]+`、`[a-zA-Z0-9_-]+`；
  - 出现过 `%`、`.`、`_`、`$`、`'` 等字符时，单独加入字符集。
- 文件扩展名单独写成字面量，例如 `[a-z0-9-]+\.html`。
- query 保持样本中参数的顺序；值固定的写字面量，值变化的写字符集；值按**原始编码形式**处理（`%3A` 就是 `%3A`，不要解码成 `:`）。

示例（仅说明写法，不代表任何真实网站）：
`^https://www\.example\.com/insights/[a-z0-9-]+/$`

### 第 8 步：实际运行 RE2 测试

**有 Python 时（推荐）**：`pip install google-re2`，然后运行下面的脚本。脚本只做机械比对：

```python
# test_re2.py —— 输入 tests.json，输出每对结果与各 split 的指标
import json, sys, importlib.metadata, re2
spec = json.load(open(sys.argv[1], encoding="utf-8"))
rx = {r["id"]: re2.compile(r["pattern"]) for r in spec["rules"]}
res, cnt = [], {}
for t in spec["tests"]:
    act = rx[t["rule_id"]].fullmatch(t["url"]) is not None
    exp = t["expected"]
    k = (t["rule_id"], t["split"])
    c = cnt.setdefault(k, {"TP": 0, "FP": 0, "FN": 0, "TN": 0})
    c[("T" if exp == act else "F") + ("P" if act else "N")] += 1
    res.append({**t, "actual": act, "pass": exp == act})
ratio = lambda a, b: None if b == 0 else a / b
metrics = [{"rule_id": r, "split": s, **c,
            "accuracy": ratio(c["TP"] + c["TN"], sum(c.values())),
            "precision": ratio(c["TP"], c["TP"] + c["FP"]),
            "recall": ratio(c["TP"], c["TP"] + c["FN"])} for (r, s), c in sorted(cnt.items())]
json.dump({"engine": "google-re2", "version": importlib.metadata.version("google-re2"),
           "results": res, "metrics": metrics}, sys.stdout, ensure_ascii=False, indent=1)
```

`tests.json` 的格式：

```json
{"rules": [{"id": "S1-R51-E1-F1", "pattern": "^https://www\\.gartner\\.com/en/marketing/insights/[a-z0-9-]+$"}],
 "tests": [{"rule_id": "S1-R51-E1-F1", "url": "https://...", "expected": true,  "split": "inference", "identity": "normal"},
           {"rule_id": "S1-R51-E1-F1", "url": "https://...", "expected": true,  "split": "holdout",   "identity": "normal"},
           {"rule_id": "S1-R51-E1-F1", "url": "https://...", "expected": false, "split": "holdout"}]}
```

`split` 只有三种取值：`inference`（归纳）、`holdout`（留出）、`regression`（回归，即已经看过的旧留出样本）。

**无代码方式**：如果环境里无法运行 RE2，可以人工或用其他正则引擎逐对判断。但这种结果**只能算候选**，规则验证状态写“待验证（未在 RE2 上运行）”。
不能把 JavaScript 或 Python `re` 的通过结果说成 RE2 通过。

### 第 9 步：落地身份核验（正例必须真的是该栏目的页面）

测试里每个**期望匹配**的样本都要实际打开，并记录状态码、最终 URL 和标题：

- 正常：200、有标题，且最终 URL 与请求 URL 相同（只差尾斜杠的跳转也算正常）。
- 跳到别的页面（例如回到列表页，或跳到其他栏目）：**不能当正例**。记录跳转链，并在备注中说明。
- 404 或 5xx：sitemap 里的死链很常见，**不能当正例**。按落地结果剔除，并单独记录。
  剔除只能看页面自身的状态，不能看规则匹配的结果。
- 页面标题可能在很大的 `<head>` 后面才出现，要在整个 HTML 中查找，不要只看前几十 KB。

### 第 10 步：覆盖检查

把规则拿去匹配以下两组 URL：

- 该家族的**全部列表成员**（所有分页）；
- sitemap 中**同结构**的全部 URL（尾斜杠按第 6 步的判定）。

任何一个匹配不上，都算“已知漏配”。还要检查规则有没有匹配到 sitemap 里结构不同的 URL，如果有，就是“可能误配”。

### 第 11 步：修订（v2）——只能有限地放宽

如果出现漏配，并且**没有任何误配**：

1. 只根据漏配样本本身的字符扩展变量字符集。漏配只是尾斜杠不同、且有跳转证据时，才把末尾改成 `/?`。
2. v1 的留出样本已经看过了，全部转为 `regression`（回归集）。
3. 重新抽取**从未用过**的留出正例和反例。实在没有新样本时，在扩展**之前**留出一半漏配样本，只用另一半扩展。
4. 重新执行第 8–10 步。

出现**误配**时不能放宽：要么收紧规则，要么降级为候选，并写明原因。

### 第 12 步：判定规则状态

| 状态 | 条件 |
|---|---|
| **已验证**（可写入 Pattern 正则列） | ① 实际运行了 RE2，并记录版本；② 归纳正例 ≥ 3、留出正例 ≥ 1、留出反例 ≥ 3；③ 所有正例都通过落地身份核验；④ 归纳、留出、回归中**所有**测试对都通过；⑤ 留出集准确率、精确率、召回率均 ≥ 95%；⑥ 覆盖检查没有漏配，也没有匹配到结构之外的 URL；⑦ 归纳样本没有跳到家族之外的页面 |
| 部分验证（候选） | 结构合理，但上面某项不满足，例如没有独立留出样本 |
| 验证不通过 | 留出集出现误配或漏配，且无法在不放宽的前提下修正 |
| 链接保留 | 同结构目标只有 1–3 个，或位于共享路径，或证据不足 |

留出样本很少（例如 6 正 3 反）时，指标是 100% 也**不能**外推为总体可靠，交付时要注明样本数量。

### 第 13 步：判定发现覆盖（该入口的内容找全了没有）

| 状态 | 条件 |
|---|---|
| 完整 | 翻页和加载更多都到底了，与 sitemap 或页面总数对账一致 |
| 完整（列表 + sitemap 合并枚举） | 列表只展示了一部分，但 sitemap 已完整遍历，而且已验证的规则能匹配 sitemap 里该家族的全部成员 |
| 完整（枚举结束，无独立全集对账） | 翻页和加载更多都到底了，但没有任何独立总数可以核对 |
| 部分 | 还有未翻完的页、未处理的动态内容、未解释的差额，或者规则未验证导致 sitemap 差额无法解释 |
| 未验证 | 入口打不开或需要登录 |

---

## 5. 前几轮踩过的坑（请逐条对照）

1. **页码被服务器忽略**：Forrester 的 `/page/2/` 返回的内容和第 1 页完全相同。真正的翻页是 “More posts” 按钮调用的接口。
   → 一定要比较第 1、2 页的内容。
2. **界面提前隐藏“加载更多”**：YouGov 的接口总数是 2,717，但页面在显示 2,660 条时就隐藏了按钮。
   用页面**自己使用的同一个只读接口**取下一个 offset，补齐了 57 条，并逐条打开确认。
   → 页面显示的条数和接口总数对不上时，要查最后一批。
3. **尾斜杠跳转**：Optimizely 列表里的链接带斜杠，打开后 308 跳到不带斜杠的地址。两种形式都是真实的匹配对象，规则要同时覆盖。
4. **尾斜杠代表不同页面**：GWI 的 `/reports/{slug}` 是报告页，而 `/reports/{slug}/` 是指南页（不带斜杠的会 301 跳过去），后者不在报告列表里。
   → 只有在第 6 步的跳转证据成立时，才把两种形式视为同一页面。
5. **大写字母、连续连字符**：Optimizely 的真实 slug 中有 `AI-experimentation`、`website--app`、以 `-` 结尾的写法。
   → 字符集只按实际样本扩展，并通过覆盖检查来发现这类遗漏。
6. **列表链接已失效**：Contentsquare 有 3 个列表链接打开后回到 `/blog/` 或其他栏目。
   → 记录下来，交给人决定是否接受，不要直接当作正例。
7. **规则匹配到了列表页本身**：Census 的入口会跳到 `/retail/index.html`，ITU 的入口是 `/Pages/default.aspx`，它们和详情页的结构相同。
   → 留出反例中要包含入口页本身；被匹配到时如实判为验证不通过，不要改标签。
8. **sitemap 地址会跳到别处**：Landor sitemap 里的 `/en/our-work/x` 会跳到 `/our-work/x/`。
   → 落地页在规则之外的，不能当正例。
9. **门户页的子页面跳转**：WIPO 不少子页面会 302 跳到补了 `/index` 的地址；Mintel 的地区链接会跳到无关的旧活动页。
   → 跳转前、中间各跳、最终页是不同的匹配对象，都要登记。
10. **sitemap 的坑**：子文件地址里的 `&amp;` 未还原导致空转；带 `#new_tab` 这类锚点；列着已经 404 的死链；请求太快被限流（403）。
11. **页面没有普通链接**：Circana Insights 用 Wix 搭建，内容条目不是 `<a href>`，也没有独立 sitemap。
    可以尝试：观察页面自己发出的数据请求（浏览器开发者工具的 Network 面板），或者逐个点击卡片、记录落地 URL。
    两种方法都不行时，写“未验证：脚本组件渲染，无可枚举链接”。

---

## 6. 交付格式（务必严格按此格式，便于合并回总表）

提交一个 `results-46.json`，外加证据文件。`results-46.json` 的结构如下：

```json
{
  "generated_at": "2026-11-01T10:00:00Z",
  "executor": "公司 AI 名称 / 版本",
  "engine": {"name": "google-re2", "version": "1.1.x"},
  "entries": [
    {
      "entry_id": "S1-R51-E1",
      "entry_url": "https://www.gartner.com/en/marketing/insights",
      "access": {"status": 200, "final_url": "…", "title": "…", "observed_at": "…", "method": "浏览器 / 授权账号 / 无法访问",
                 "note": "需人工通过验证 / 访问受限原因"},
      "prefix": "/en/marketing/insights/",
      "discovery_status": "完整 | 完整（列表+sitemap 合并枚举） | 完整（枚举结束，无独立全集对账） | 部分 | 未验证",
      "discovery_note": "翻了几页、加载更多点了几次、显示总数与实际条数、sitemap 遍历情况、差额及原因",
      "rules": [
        {
          "rule_id": "S1-R51-E1-F1",
          "pattern": "^https://…$",
          "status": "已验证 | 部分验证（候选） | 验证不通过",
          "target": "该规则覆盖什么（例如：该栏目文章详情页）",
          "variables": {"seg1": "[a-z0-9-]+ —— 依据：…"},
          "slash_mode": "slash | none | optional（附跳转证据）",
          "samples": {"inference": ["…"], "holdout_pos": ["…"], "holdout_neg": ["…"], "regression_pos": [], "regression_neg": []},
          "holdout_source": "sitemap | later_pages | other_pages | listing_split",
          "frozen_sha256": "…",
          "metrics": {"holdout": {"TP": 0, "FP": 0, "FN": 0, "TN": 0, "accuracy": 1.0, "precision": 1.0, "recall": 1.0}},
          "coverage": {"listing_members": 0, "listing_missed": [], "sitemap_same_structure": 0, "sitemap_missed": [],
                       "matched_outside_structure": []},
          "version": 1,
          "history": [],
          "why_not_verified": []
        }
      ],
      "retained_links": [{"url": "…", "reason": "共享路径 / 少于 4 个同结构 / 跳到家族外 / 文件 / 需登录"}],
      "redirects": [{"from": "…", "chain": [301, 200], "to": "…"}],
      "match_examples": ["已落地核验的正例 URL（标题，200，日期）"],
      "risks": ["快照时效、共享路径、需要人决定的范围问题等"]
    }
  ]
}
```

证据文件（每个站点一个文件夹，或者打包成 zip）：

- `visits.jsonl`：每次请求的时间、URL、每一跳的状态码、最终 URL、标题；
- `links.jsonl`：第 3 步记录的全部链接及来源关系；
- `sitemaps/`：每个站点的 URL 清单，以及遍历摘要（读了哪些文件、哪些失败、是否完整）；
- `tests.json` 和 `re2-results.json`：每条规则的冻结样本与 RE2 运行结果；
- `identity.jsonl`：第 9 步中每个正例的落地核验结果。

---

## 7. 交付前自查清单

- [ ] 46 个 `entry_id` 都在 `results-46.json` 中，一个不少，即使是“未验证”也要列出。
- [ ] 每条“已验证”的规则都满足第 12 步的全部 7 项条件，并附有 RE2 版本和运行结果。
- [ ] 正则都以 `^` 开头、`$` 结尾，没有 `.*`、前瞻/后顾或反向引用，并且在 RE2 上编译通过。
- [ ] 没有为了通过测试而修改样本标签；v1 留出样本在 v2 中只作为回归集使用。
- [ ] 所有正例都通过了落地核验；跳转到别处的、404 的都已剔除并记录原因。
- [ ] 共享路径（不在入口前缀下）的链接没有被泛化，只保留了链接。
- [ ] 每个入口的覆盖状态都写明了依据：翻了几页、点了几次、总数是多少、差额多少、原因是什么。
- [ ] 交付物中没有 Cookie、Token、账号或其他认证信息。
- [ ] 最后用一段话汇报，并且**分开计数**：入口完成多少、已验证规则多少、候选多少、保留链接多少、访问受限多少、主要缺口是什么。
  不要把不同维度合并成一个“完成率”。
