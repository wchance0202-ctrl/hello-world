# 任务：补齐剩余栏目入口的 URL 收录正则，并核验覆盖

> 使用说明：把这份文件（包括末尾附录）和 `remaining-tasks.xlsx` 一起交给执行任务的 AI。
> 它需要一个能**以正常身份打开网页**的环境，例如公司网络里的浏览器，或已获授权的账号。
> 能运行 Python 更好，因为第 8 步要实际运行 RE2。如果不能运行代码，可以按第 8 步的“无代码方式”执行，但这样得到的规则只能算候选，交付时必须说明。

---

## 0. 背景与目标

我们在维护一张表。表里「指定pattern」列的每个单元格是一个或多个**栏目入口 URL**，例如某网站的报告列表页或资讯频道首页。
每个入口都有一个全局唯一的 `entry_id`：第一批是 `S1-R{行}-E{序号}`，第二批是 `S2-R{行}-E{序号}`。

对每个入口，需要交付三样东西：

1. **Pattern 正则**：匹配该栏目**自己的页面**的正则。必须兼容 RE2，匹配完整 URL。“自己的页面”指什么，第 1 节有严格定义。
2. **保留链接**：确实属于该栏目、但无法用正则安全覆盖的 URL，原样逐条列出。
3. **核验证据**：每条正则都要用真实样本测试过；每个入口都要说明栏目内容有没有找全。

两批共 535 个入口，大部分已经处理完毕。还剩 **175 个入口、208 条任务**交给你，分成 10 类：

| 类型 | 含义 | 第一批 | 第二批 |
|---|---|---|---|
| T1 | 入口没打开：站点防护拦截、超时、证书错误、代理错误、挑战页 | 46 | 25 |
| T2 | 页面里没有标准 `<a href>` 链接，内容由脚本组件渲染 | 1 | 12 |
| T3 | 栏目边界内没有可归纳的下级页面；条目可能都在边界外，需要重判边界 | — | 21 |
| T4 | 列表只取到首屏或前几屏，脚本翻页或加载更多没有走到底 | — | 8 |
| T5 | Hash 路由列表的翻页或加载更多没有枚举 | — | 7 |
| T6 | 分页没翻完：上一轮单入口最多请求 300 页 | — | 5 |
| T7 | sitemap 对账有缺口：sitemap 里有同结构 URL，但列表里没有 | — | 10 |
| T8 | 已有候选规则，但没达到正式准入条件 | 8 | 16 |
| T9 | 规则验证不通过：规则匹配到了同级栏目页 | — | 10 |
| T10 | **已交付的规则范围超界**：边界退化成站点根 `/`，或者用变量覆盖了栏目标识，需要按第 1 节重做 | — | 39 |

逐条清单见本文末尾的附录。完整字段在 `remaining-tasks.xlsx` 里，包括上一轮的记录和已有的正则。

**最重要的原则是只交付有证据的结论。**
看不到的就写“未验证”。不猜测，不编造，也不要把少量样本的结果说成全部。

---

## 1. 提取对象的范围（最重要，请先读懂这一节）

这一节回答一个问题：**一条正则到底应该匹配哪些 URL？**
上一轮出过的范围问题，全部源于这里没有把握住，所以请逐条执行。

### 1.1 一句话定义

> 一条正则的匹配对象，是**某一个入口栏目自己的页面的完整 URL**。
> 也就是说，这个 URL 要同时满足两点：
> ① 能从该入口出发、经由栏目主体内容区（包括翻页、加载更多和子栏目）到达，或者出现在本栏目的独立来源里；
> ② **只看 URL 本身**，就能确定它属于这个栏目，而不是同站的别的栏目。
>
> 满足 ① 但不满足 ② 的 URL 确实属于本栏目，但正则无法区分它们。这类 URL 只能逐条保留，不能写进正则。

因此，每个 URL 只会落进下面三类中的一类：

| 类别 | 含义 | 去处 |
|---|---|---|
| **A 正则对象** | 属于本栏目，并且 URL 带有本栏目的标识，可以按结构归纳 | 写进「Pattern 正则」 |
| **B 保留链接** | 确实属于本栏目，但 URL 不带本栏目的标识（全站共用的详情路径），或者同结构样本少于 4 个，或者证据不足 | 原样写进「保留链接」，并注明原因 |
| **C 不收录** | 不属于本栏目：导航、页脚、推荐位、同级栏目、站外链接、技术资源等 | 不进正则，也不进保留链接；可以作为反例使用 |

### 1.2 判定为 A 类的四个条件（必须全部满足）

1. **同源**：scheme 和 host 都与入口**实际落地页**相同。
   - `http` 和 `https` 是不同的对象，有 `www` 和没有 `www` 也是不同的对象，不能自行合并。
   - 入口如果从 `http` 跳到 `https`，A 类对象就是 `https` 形式；跳转前的 `http` 地址记在 `redirects` 里。
   - 入口没写协议的（如 `www.ctrchina.cn/product/MI`），按 `https://` 请求，并在备注中说明。
2. **在栏目边界之内**：按 1.3 节确定栏目边界。URL 要么路径落在边界前缀之内，要么带有本栏目的标识值。
3. **有来源证据**：URL 至少出现在下面一处：
   - 本栏目主体列表的任意一页；
   - 本栏目的子栏目页；
   - 同结构的 sitemap 条目，并且已经按第 10 步证明属于本栏目；
   - 本栏目列表链接的实际跳转目标。
4. **落地正常**：打开后返回 200、有标题，并且最终 URL 等于请求的 URL（只差尾斜杠的跳转除外，见第 6 步）。

### 1.3 栏目边界怎么确定

先按入口 URL 的形式确定**路径前缀**，再检查这个前缀能不能把本栏目和其他栏目区分开。

| 入口形式 | 边界 | 示例 |
|---|---|---|
| 目录形式，以 `/` 结尾 | 就是该目录 | `/news/` → `/news/` |
| 无斜杠、无扩展名，末段是栏目名 | 末段补 `/` | `/en/marketing/insights` → `/en/marketing/insights/` |
| 无斜杠、无扩展名，但**末段是列表页的页名**（如 `index`、`list`、`search`、`allType`、`topicList`、`home`、`main`） | 先看 `/x/{页名}/` 下面有没有条目。如果有，就用 `/x/{页名}/`。如果没有、条目都在 `/x/` 下，那么**只有在证明 `/x/` 专属于本栏目时**，才把边界退到 `/x/`：同站其他栏目、其他入口和导航都不使用 `/x/` 下的地址。不能证明时，条目按 B 类处理 | `jzt.jd.com/school/index` 的条目若是 `/school/detail/…`，需先证明 `/school/` 只属于这个栏目 |
| 文件形式（`.html`、`.htm`、`.shtml`、`.aspx`、`.jsp`） | 如果页面链接到 3 个以上 `/a/b/…` 下的地址，边界取 `/a/b/`，否则取上级目录 `/a/` | `/resources/reports.html` → `/resources/reports/` 或 `/resources/` |
| SharePoint 形式 | 去掉 `Pages/default.aspx` | `/en/ITU-R/Pages/default.aspx` → `/en/ITU-R/` |
| 带分页参数的入口（如 `?page=1`） | 边界按路径确定，`page` 参数当作列表分页 | `/content/whitepaper-store?page=1` → 路径 `/content/whitepaper-store` |
| 入口带普通锚点（如 `#jump`、`#industry-news`） | 去掉锚点后再按上面各行确定。如果锚点会切换页内标签，栏目就是该标签下展示的条目，并要在备注中说明 | `/publication#jump` → `/publication/` |

**两种情况下，路径边界不能用，要改用“栏目标识”：**

1. **边界退化成站点根 `/`**：例如入口是根目录下的文件 `/study_list.html`、`/list-20-1.html`、`/index.html`。
   这时“边界之内”等于整个网站，按路径泛化必然会匹配到其他栏目。**禁止**写出 `^https://www\.example\.com/[a-z_]+\.html$` 这样以整个站点为范围的正则。
2. **栏目由 query 参数、文件名中的编号或 Hash 路由参数区分**：例如 `article_list.html?type=1`、`list-20-1.html`、`channels/13.html`、`lists/800.html`、`#!/…?pkey=insight`。

此时，要先找出本栏目的**栏目标识**，也就是本栏目 URL 里独有、其他栏目不同的那个值。例如 `type=1`、`catid=20`、`pkey=insight`。然后：

- 如果**条目 URL 也带着这个标识**，标识在正则里**必须写成字面量**，只有其余部分可以是变量。
  例如入口 `list-20-1.html` 的详情是 `index.php?m=content&c=index&a=show&catid=20&id=123`。
  正确的写法是 `…&catid=20&id=[0-9]+$`；写成 `catid=[0-9]*` 就会覆盖所有栏目，属于**范围超界**。
- 如果**条目 URL 不带任何本栏目标识**，这些条目全部归入 B 类。
  例如 `type=1` 到 `type=4` 四个栏目的详情都是 `article_info.html?id=N`。此时逐条列出本栏目实际出现的 URL，不写正则。

### 1.4 哪些 URL 是对象，哪些不是

| URL 类型 | 归类 | 怎么处理 |
|---|---|---|
| 边界内的**详情页**（文章、报告、案例、课程……） | A | 按结构分家族，每个家族一条正则 |
| 本栏目的**列表分页页**（`/page/N/`、`?page=N`、`?p=N`、`list-20-2.html`） | A，单独成一个家族 | 写单独的分页正则。**详情正则不能匹配分页页**，分页页要作为详情正则的反例 |
| **入口页本身** | 不进正则 | 它是入口，作为每条规则的必备反例。如果某条规则匹配到了入口页，判为验证不通过，不能改标签 |
| 边界内的**子栏目页**（如 `/blog/category/x/`） | A，单独成家族 | 子栏目列表里的条目，只有在边界内时才算 A |
| 边界内、由主体区链接到的**文件**（PDF、XLSX 等） | 一般归 B | 同结构文件达到 4 个以上，并且每个都核验过时，才可以归纳成 A |
| 列表链接 X 跳转到 Y | X 是对象；Y 只有在边界内时才是 A | 跳转前的地址、每个中间跳、最终页都是**不同的对象**，全部记进 `redirects`。只有最终落地在家族之内，才能当正例 |
| 边界外的同站**共享路径**（如所有栏目共用的 `/articles/{id}`、`/article/N.html`、`/p/N.html`） | 来自本栏目主体列表的，归 B | 原样逐条保留。**绝对不能泛化**，因为 URL 里没有栏目信息 |
| Hash 路由的详情页（`#/…`、`#!/…`） | A（前提是 Hash 路由参数里带有本栏目标识，或者路由前缀专属本栏目） | `#` 及后面的路由和参数都是 URL 的一部分，不能丢 |
| **同级栏目页**：与入口同结构的其他栏目入口，例如 `/lists/800.html` 旁边的 `/lists/51.html`，`/channels/13.html` 旁边的 `/channels/14.html` | C | 正则不能匹配它们。规则写成 `/lists/[0-9]+\.html` 就会覆盖所有同级栏目，所以不行 |
| 页头、导航、页脚、侧栏、“相关推荐 / 热门 / 排行”、面包屑 | C | 例外：如果主体区里边界内的链接不到 3 个，可以改看 nav 或 header 里**边界内**的链接，并在记录中注明 |
| 站外链接、其他子域名 | C | — |
| 技术资源与功能链接：JS、CSS、图片、字体、接口（`/api/`、`.json`）、RSS、登录、注册、下载留资、分享（如 `service.weibo.com/share`）、`mailto:`、`tel:`、`javascript:` | C | — |
| 普通页内锚点（`#section`、`#new_tab`） | 不算独立对象 | 去掉锚点，再按剩下的 URL 判断 |
| 其他语言版本、站内搜索结果页 | C | 例外：入口本身就是搜索页或某个语言版本时，按 1.3 节处理 |

### 1.5 匹配的字符串到底是什么

- 匹配的是**完整的原始 URL**：`scheme://host[:port]/path[?query][#hash路由]`。
- 相对链接按所在页面解析成绝对地址。**只做解析，不做规范化**：
  - 不改大小写；
  - 不删、不重排 query 参数；
  - 不解码或重新编码百分号（`%3A` 保持 `%3A`）；
  - 不补、也不删尾斜杠。
- 同一页面的不同写法（带不带尾斜杠、`http` 还是 `https`、有没有 `www`、参数顺序不同）都是**不同的字符串**。
  只有在第 6 步拿到跳转证据时，才允许用 `/?` 同时覆盖带斜杠和不带斜杠两种写法。

### 1.6 上一轮的真实案例（照此判断）

| 案例 | 正确归类 |
|---|---|
| Forrester 各博客分类的文章都是 `/blogs/{slug}/`，全站共用 | B：保留链接，不泛化 |
| 界面新闻 `/lists/800.html` 是一个栏目，同站还有 `/lists/51.html`、`/lists/30.html` 等几十个同级栏目 | 同级栏目页归 C。规则 `^…/lists/[0-9]+\.html$` 会匹配到同级栏目，判为验证不通过（本次 T9）。详情如果在全站共用的路径下，就归 B |
| 中国家用电器协会 `/channels/13.html`、`/channels/14.html`…… | 同上 |
| 中国煤炭工业协会 `list-20-1.html` 的详情是 `index.php?…&a=show&catid=20&id=N` | A，但正则里 `catid=20` 必须写成字面量。上一轮写成 `catid=[0-9]*`，属于范围超界（本次 T10） |
| 甲子光年 `article_list.html?type=1` 到 `type=4` 的详情都是 `article_info.html?id=N`，不带 type | B：每个栏目逐条保留自己列表里出现的详情 URL。上一轮写成共用正则，属于范围超界（本次 T10） |
| 投中网入口 `/index.html`，规则写成 `^…/[a-z]+/[a-z0-9_-]+\.html$` | 范围是整个站点，属于超界（T10）。要找出栏目专属的目录或标识，找不到就归 B |
| 阿里妈妈 `#!/marketing-insight/index` 栏目的详情落在 `#!/marketing-wiki/article-detail?id=…&pkey=insight&skey=ai` | A：`pkey=insight` 是栏目标识，写成字面量。`skey` 只观察到一个取值时也写成字面量；如果页面上还有其他子分类没取样，就只能算候选，并写明原因 |
| Optimizely 列表链接带尾斜杠，打开后 308 跳到不带斜杠的地址 | A：两种写法都是对象，正则末尾写 `/?`，证据是这次跳转 |
| GWI 的 `/reports/{slug}` 是报告页；`/reports/{slug}/` 是指南页，不在报告列表里 | 不带斜杠的是 A，带斜杠的归 C。**不能**写 `/?` |
| Census 入口跳到 `/retail/index.html`，详情是 `/retail/xxx.html`，与入口页同结构 | 入口页本身归 C，作为反例。规则匹配到入口页时，如实判为不通过；如果只有入口页这一个误配，整组改为 B 类保留链接 |
| Contentsquare 有 3 个列表链接，打开后回到 `/blog/` 或跳到其他栏目 | 不能当正例。记录跳转链，交给人决定 |

---

## 2. 访问边界（必须遵守）

- 只做**只读访问**：打开页面、翻页、点击“加载更多 / More / 查看更多”这类展示按钮。
  不提交表单；不注册、订阅，也不下载需要留资的内容；不点赞、收藏，也不联系销售。
- **不绕过任何访问限制**。遇到验证码、登录墙、付费墙、“Access Denied”或“Just a moment...”这类页面：
  - 能人工通过的，记录为“需人工通过”；
  - 过不了的，记为**访问受限**，然后跳过。
  - 不要使用伪装浏览器指纹、代理轮换、打码服务或网页存档副本这类绕过手段，也不要关闭 TLS 证书校验（例如 `chinapv.org.cn` 的证书链问题，如实记录即可）。
- 公司已订阅的站点（如 Crunchbase、PitchBook、Dealroom、启信宝 VIP），可以用**有权使用的账号**登录访问。
  交付物里不得出现 Cookie、Token、账号或任何认证信息。
- 控制速度：同一站点同一时间只开一个页面，相邻请求至少间隔 1–2 秒。连续出现 429 或 403 时，立即停止访问该站点并记录。
- 同一网站的多个入口要**串行**处理，并共用“已访问”记录。例如 Dealroom 10 个、联商网 10 个、中国家用电器协会 7 个、中国煤炭工业协会 16 个。

---

## 3. 匹配契约（所有正则共同遵守）

- 匹配对象是**完整 URL**（见 1.5 节）。
- 每条正则都以 `^` 开头、以 `$` 结尾，区分大小写，不对 URL 做任何规范化。
- 只能使用 RE2 支持的语法：**不能用**前瞻或后顾（`(?=` `(?!` `(?<=` `(?<!`），也不能用反向引用（`\1`）。
- 字面量必须转义，如 `.` 写成 `\.`，`?` 写成 `\?`，`#` 写成 `\#`，`-` 写成 `\-`。
- **禁止**用 `.*`、`.+`、`(?:[?#].*)?` 或不限层级的路径来凑覆盖率。每个变量段都必须有依据：它的字符集、层级和参数名都要能在样本里找到。
- 不要无依据地放宽协议、`www`、尾斜杠、大小写或参数顺序。
- 栏目标识必须写成字面量（见 1.3 节）。

---

## 4. 处理流程（逐个入口执行，每一步都要留记录）

### 第 1 步：打开入口，记录身份

- 记录：请求 URL、每一跳的状态码和 Location、最终 URL、最终状态码、页面标题、H1、正文是否正常。
- 判断页面类型：
  - 正常页；
  - 挑战页或登录页；
  - 软 404：状态码 200，但内容是“页面不存在”；
  - 空壳：只有页头页脚，主体由脚本加载。
- 打不开就停在这一步：链接状态写“访问受限”，并附上原因和观察时间。

### 第 2 步：确定栏目边界

按 1.3 节确定边界，并把边界类型和依据写进 `scope`：

- 路径前缀；
- 页名退到上级（附专属证据）；
- 栏目标识（附标识值，以及它在其他栏目中的不同取值）；
- 无可用边界（全部归 B）。

### 第 3 步：枚举栏目内容（要找全）

1. 只看页面**主体区域**的链接，排除页头、导航、页脚和侧栏。例外情况见 1.4 节。
2. **翻页与加载更多**：
   - 识别分页链接（`/page/N/`、`?page=N`、`?p=N`、`?offset=N`、`list-20-N.html` 等），一直翻到最后一页。只跟随边界内的分页，不要翻到其他语言或其他栏目。
   - 有“加载更多 / More / Show more”按钮的，反复点击，直到按钮消失，或者连续 3 次没有新内容。
   - 需要滚动加载的，一直滚到不再出现新内容。
   - **核对页码是否真的生效**：比较第 1 页和第 2 页的主体链接集合。完全相同，就说明服务器忽略了页码，要去找真实的加载方式，例如按钮背后的接口。
3. **对账总数**：如果页面上显示了总数（如“共 606 条”），或者页面自己的接口返回了 `total`、`count`，要和实际取到的条目数对比。差额必须找到原因；找不到原因，就如实写“差 N 条未解释”。
4. 每条链接都要记录：`entry_id`、`parent_url`（在哪一页发现）、`raw_href`（原始写法）、`resolved_url`（解析后的完整地址）、所在区域、链接文字、关系类型，以及按第 1 节判定的 **A、B、C 类别**。
5. **没有 `<a href>` 的页面**（T2，以及 T5 的 Hash 路由）：
   - 用浏览器开发者工具的 Network 面板，观察页面**自己发出的只读数据请求**，从返回的条目 id 推出详情 URL。这样推出的 URL 必须逐个实际打开核验，未核验的不能当正例。
   - 或者逐个点击卡片，记录落地 URL（包括新标签页）。
   - 两种办法都不行时，写“未验证：脚本组件渲染，无可枚举链接”。

### 第 4 步：收集独立来源（用于验证，必须和列表页分开）

按以下顺序收集，供第 6 步抽取留出样本：

1. **sitemap**：先读 `robots.txt` 里的 `Sitemap:` 行；没有的话，依次尝试 `/sitemap.xml`、`/sitemap_index.xml`、`/sitemap-index.xml`。
   - sitemap 索引要递归展开，`.gz` 要解压；
   - `<loc>` 里的 `&amp;` 要先还原成 `&`；
   - 去掉普通锚点；
   - 记录读了哪些文件、哪些失败；
   - 所有子文件都读完，才能说“已完整遍历”。
2. **后续分页**：如果列表只有入口首页这一页，就没有这个来源。
3. **同站其他页面上出现的链接**：其他入口的页面，或者详情页上的“相关文章”。

### 第 5 步：按 URL 结构分组（找“家族”）

只对 **A 类候选 URL** 分组。入口页本身、分页页、B 类和 C 类都不参与。分组依据是**结构签名**：

- 边界之后有几段路径；
- 是否带尾斜杠；
- query 的参数名及顺序；
- 文件扩展名；
- 栏目标识的值。

规则：

- 同一签名下有 **≥ 4 个**不同的 URL，才算一个可以泛化的家族。
- 只有 1–3 个同结构目标的，**不要强凑正则**，直接归入 B 类。
- 同一路径位置上，如果所有样本取值都相同，就按字面量处理；取值不同的才是变量。
  例如样本里只出现过 `2026`，就不能凭此推断这个位置是变量。

### 第 6 步：先冻结样本，再归纳

在写正则**之前**，先把三组样本定下来并保存，附上文件的 sha256 和保存时间：

- **归纳集**：
  - 有 sitemap 可以作留出时，用列表页上的全部成员；
  - 没有 sitemap 时，只用入口首页上的成员，后续分页留作验证。
- **留出正例**：每个家族 1–6 个，不能出现在归纳集里，用固定随机种子抽取。来源按以下优先级：
  1. sitemap 里结构相同、但列表里没有的 URL；
  2. 后续分页上的成员；
  3. 同站其他页面上出现的同结构链接；
  4. 以上都没有时，在归纳**之前**按固定种子从列表成员中随机拆出约 1/4（至少 1 个，最多 6 个）。成员不足 4 个时不能拆分。
- **留出反例**：至少 3 个，必须是同站**真实存在**的 URL。下面几类优先，并尽量各取一个：
  - 入口页本身和分页页；
  - **同级栏目页**；
  - 栏目标识取其他值的同结构 URL，例如 `catid=21` 的详情；
  - 边界外、路径层级相同的同站页面；
  - 边界内其他家族的成员。

**尾斜杠的判定**：只有**归纳样本自己的跳转**证明两种写法指向同一页面时，才算同一家族，正则末尾写 `/?`。否则，尾斜杠不同就是不同类型的页面。

**冻结之后，绝对不能为了让测试通过而修改任何样本的期望标签。**

### 第 7 步：写正则

- 写法：`^` + 转义后的协议与主机 + 转义后的边界前缀 + 各段（字面量段转义，变量段用字符集）+ 尾斜杠处理 + query + `$`。
- 变量段的字符集，只取**归纳集里实际出现过的字符类别**：
  - 全是数字，用 `[0-9]+`；
  - 其他情况按实际出现的字符组合，如 `[a-z0-9-]+`、`[a-zA-Z0-9_-]+`；
  - 出现过 `%`、`.`、`_` 等字符的，单独加进字符集。
- 文件扩展名写成字面量，例如 `[a-z0-9-]+\.html`。
- query 保持样本中参数的顺序：值固定的写字面量，值变化的写字符集，值按原始编码形式处理。**栏目标识一律写成字面量。**

示例（仅说明写法，不代表任何真实网站）：

- 路径边界：`^https://www\.example\.com/insights/[a-z0-9-]+/$`
- 栏目标识：`^https://www\.example\.cn/index\.php\?m=content&c=index&a=show&catid=20&id=[0-9]+$`

### 第 8 步：实际运行 RE2 测试

**有 Python 时（推荐）**：先 `pip install google-re2`，然后运行下面的脚本。脚本只做机械比对：

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
{"rules": [{"id": "S2-R109-E4-F1", "pattern": "^https://www\\.coalchina\\.org\\.cn/index\\.php\\?m=content&c=index&a=show&catid=20&id=[0-9]+$"}],
 "tests": [{"rule_id": "S2-R109-E4-F1", "url": "https://…", "expected": true,  "split": "inference", "identity": "normal"},
           {"rule_id": "S2-R109-E4-F1", "url": "https://…", "expected": true,  "split": "holdout",   "identity": "normal"},
           {"rule_id": "S2-R109-E4-F1", "url": "https://…", "expected": false, "split": "holdout"}]}
```

`split` 只有三种取值：

- `inference`：归纳集；
- `holdout`：留出集；
- `regression`：回归集，即已经看过的旧留出样本。

**无代码方式**：如果环境里不能运行 RE2，可以人工或用其他正则引擎逐对判断。但这样得到的结果**只能算候选**，规则验证状态写“待验证（未在 RE2 上运行）”。
不能把 JavaScript 或 Python `re` 的通过结果说成是 RE2 通过。

### 第 9 步：落地身份核验

测试里每个**期望匹配**的样本都要实际打开，并记录状态码、最终 URL 和标题：

- **正常**：200、有标题，并且最终 URL 等于请求 URL（只差尾斜杠的跳转也算正常）。
- **跳到别处**：例如回到列表页或跳到其他栏目。这种样本**不能当正例**，要记录跳转链。
- **404 或 5xx**：sitemap 里的死链很常见，**不能当正例**，按落地结果剔除并单独记录。
  剔除只看页面本身的状态，不看规则匹配的结果。
- 页面标题可能出现在很大的 `<head>` 之后，要在整个 HTML 里查找。
- Hash 路由页：HTTP 状态码对所有路由都一样，无法区分。必须**单独在浏览器里打开**这个 URL（不经过点击），确认卡片标题出现在渲染后的正文中。

### 第 10 步：覆盖检查

把规则拿去匹配以下两组 URL：

- 该家族的**全部列表成员**（所有分页）；
- sitemap 里**同结构**的全部 URL。

匹配不上的，都算“已知漏配”。还要检查规则有没有匹配到 C 类 URL，或者 sitemap 里结构不同的 URL。有的话，就是“可能误配”。

sitemap 里同结构、但列表里没有的 URL（T7），要逐个判断是不是本栏目的成员：

- 打开后看面包屑、栏目标签，或者它是否出现在列表的后续页里；
- 属于本栏目的，算覆盖；
- 不属于的，说明这个结构为什么不能区分栏目。这种情况通常说明边界有问题，要回到第 2 步。

### 第 11 步：修订（v2），只能有限地放宽

出现漏配、并且**没有任何误配**时：

1. 只根据漏配样本本身的字符扩展字符集。如果漏配只是尾斜杠不同，必须有跳转证据，才能把末尾改成 `/?`。
2. v1 的留出样本已经看过了，全部转为 `regression`（回归集）。
3. 重新抽取**从未用过**的留出样本。实在没有新样本时，在扩展**之前**留出一半漏配样本，只用另一半来扩展。
4. 重新执行第 8–10 步。

出现**误配**时不能放宽。要么收紧规则，要么降级为候选，并写明原因。

### 第 12 步：判定规则状态

| 状态 | 条件 |
|---|---|
| **已验证**（可以写进 Pattern 正则列） | 以下 8 项全部满足：<br>① 实际运行了 RE2，并记录了版本；<br>② 归纳正例 ≥ 3、留出正例 ≥ 1、留出反例 ≥ 3；<br>③ 所有正例都通过了落地核验；<br>④ 归纳、留出、回归集中的**所有**测试对都通过；<br>⑤ 留出集的准确率、精确率、召回率都 ≥ 95%；<br>⑥ 覆盖检查没有漏配，也没有匹配到结构之外的 URL；<br>⑦ 归纳样本没有跳到家族之外；<br>⑧ **范围不超界**：边界不是站点根 `/`，栏目标识写成了字面量，并且不匹配入口页、同级栏目页和栏目标识取其他值的 URL |
| 部分验证（候选） | 结构合理，但上面某一项不满足，例如没有独立的留出样本 |
| 验证不通过 | 留出集出现误配或漏配，并且不放宽就无法修正 |
| 链接保留 | B 类：同结构目标只有 1–3 个，或者位于共享路径、不带栏目标识，或者证据不足 |

留出样本很少时（例如 6 个正例、3 个反例），即使指标是 100%，也**不能**外推为总体可靠。交付时要注明样本数量。

### 第 13 步：判定发现覆盖（该入口的内容找全了没有）

| 状态 | 条件 |
|---|---|
| 完整 | 翻页和加载更多都到底了，并且与 sitemap 或页面总数对账一致 |
| 完整（列表+sitemap 合并枚举） | 列表只展示了一部分，但 sitemap 已完整遍历，并且已验证的规则能匹配 sitemap 里该家族的全部成员 |
| 完整（枚举结束，无独立全集对账） | 翻页和加载更多都到底了，但没有任何独立的总数可以核对 |
| 部分 | 还有没翻完的页、没处理的动态内容、没解释的差额，或者规则未验证，导致 sitemap 差额无法解释 |
| 未验证 | 入口打不开，或者需要登录 |

---

## 5. 各类任务的要点

- **T1 入口未打开**：
  - 第一批的 45 个大多是 Cloudflare、Akamai 拦截或连接超时，例如 BLS、McKinsey、BCG、Gartner、Dealroom；
  - 第二批有联商网 10 个（上游超时），以及数说故事 468、启信宝 451、syntun、vzkoo、digitaling、huiju 返回 403，iyiou 返回 202 挑战页、微播易代理错误、CSM 连接被重置、中国光伏证书链错误等。
  - 已知线索（需要复核，不能直接当结论）：
    - Gartner 的部分 `/insights/` 列表链接会跳到 `/research/`、`/articles/`，按 1.4 节的跳转规则处理；
    - Crunchbase `discover`、Dealroom `companies/` 和 `investors/`、启信宝 `pay/vip` 很可能是需要登录的数据库应用页。没有授权账号时，只保留入口本身，结果类型写“链接保留”，覆盖状态写“未验证（需登录）”。
- **T2 无标准链接**：例如 Circana（Wix）、头豹 `report/search`、研报客、小红书 `numerous`、抖音创作者中心 `arithmetic-index`、京东 survey、人人都是产品经理 `harmony`、分众 `publication`、Mob 研究院、新榜。按第 3 步第 5 条处理。
- **T3 边界内无下级家族**：例如 `jzt.jd.com/school/index`（边界外同站链接有 117 个）、`www.ctrchina.cn/report`、蝉妈妈、分众传媒。
  - 这类入口重点看 1.3 节中“页名”那一行：条目在 `/x/` 下时，只有证明 `/x/` 专属于本栏目，才能退到 `/x/`；
  - 不能证明的，主体区条目逐条归 B，正则留空，并写明原因。
- **T4 列表未到底**：例如 CBNData `report`（渲染翻到 `?page=21` 后停止）、飞瓜 `StudyReport`、京准通 `gw/information`、Morketing、人人都是产品经理 `fish`、艾瑞 `Research.shtml`、新榜 `trade/news`。在浏览器里走到底，并对账总数。
- **T5 Hash 路由**：快手磁力 3 个、阿里妈妈 3 个、incoPat 1 个。
  - 上一轮只点了首屏 6–8 张卡片；
  - 要翻完列表，扩大样本，每个都单独打开核验；
  - 阿里妈妈 `skey` 的其他取值需要补样本（1.6 节）。
- **T6 分页未翻完**：
  - 增长黑客 `cgo`（已请求 929 页，还剩 1 页待访问）、`quan`；
  - Foodaily `articles` 和 `newsflashes`；
  - 沙利文 `whitepaper-store`（还有 16 页待访问）。
  - 接着上一轮翻到底，然后重跑覆盖检查。
- **T7 sitemap 对账缺口**：例如增长黑客 `cgo` 的 sitemap 有 4,205 个同结构 URL 不在列表里，`quan` 有 5,488 个；神策 `blog`、`school/library`；飞瓜快手 `news`。按第 10 步逐个判断归属。
  如果 sitemap 里的同结构 URL 明显包含其他栏目，就说明这个结构不能区分栏目，要回到第 2 步。
- **T8 候选规则**：
  - 缺独立留出的（ITU、D&AD、GrowthHackers、Siegel+Gale、飞瓜快手 `news` F2、煤炭协会 list-20/42）：找 sitemap、后续分页或其他页面上的同结构样本；
  - 归纳正例不足 3 个的（WIPO `patentscope`）：补归纳样本，补不到就归 B；
  - 留出与归纳重叠、样本重复的（WIPO `business`、Euromonitor、Comscore、飞瓜、前瞻 F2、神策 `blog` F2、煤炭协会 list-41、纺织联合会、KOLKOC）：重新抽样；
  - 缺落地核验的（CTR、前瞻）：补核验；
  - 留出反例不足 3 个的（小红书 `case`、TalkingData）：补反例；
  - 阿里妈妈 `marketing-wiki`：`skey` 只取到一个值，补其他子分类的样本。
- **T9 验证不通过**：界面新闻 3 个、中国家用电器协会 7 个。规则匹配到了同级栏目页，按 1.6 节改判。
- **T10 范围超界**：甲子光年 `jazzyear` 6 个入口、投中网 1 个、中国煤炭工业协会 16 个入口，共 39 条规则。
  - 逐条按 1.3 节重做：找出栏目标识，并写成字面量；条目里没有标识的，改为 B 类保留链接；
  - 新规则要重新走第 6–12 步；
  - 交付时在 `replaces` 字段写明它替换了哪条旧规则。

---

## 6. 前几轮踩过的坑（请逐条对照）

1. **页码被服务器忽略**：Forrester 的 `/page/2/` 和第 1 页内容完全相同，真正的翻页是“More posts”按钮调用的接口。一定要比较第 1、2 页的内容。
2. **界面提前隐藏“加载更多”**：YouGov 接口的总数是 2,717，但页面显示到 2,660 条时就隐藏了按钮。显示条数和总数对不上时，要用页面自己使用的同一个只读接口查最后一批。
3. **尾斜杠**：Optimizely 的两种写法是同一页（有 308 跳转为证）；GWI 的两种写法是不同的页面。
4. **大写字母、连续连字符**：Optimizely 的 slug 里有 `AI-experimentation`、`website--app`，还有以 `-` 结尾的写法。字符集只按实际样本扩展。
5. **列表链接已失效**：跳到别处的链接，不能当正例。
6. **规则匹配到入口页本身或同级栏目页**：如 Census、ITU、界面新闻、中国家用电器协会。这两类一定要放进反例。
7. **边界退化成站点根 `/`**：入口是根目录下的文件，或者栏目由 query 区分。必须用栏目标识（1.3 节）。
8. **sitemap 地址会跳到别处**：Landor sitemap 里的 `/en/our-work/x` 会跳到 `/our-work/x/`。落地页在规则之外的，不能当正例。
9. **门户页的子页面跳转**：WIPO 的子页面会 302 跳到补了 `/index` 的地址。跳转前、各个中间跳和最终页是不同的对象。
10. **sitemap 的坑**：`&amp;` 没还原导致反复请求同一个索引；带 `#new_tab` 这类锚点；列着已经 404 的死链；请求太快被限流。
11. **JSONL 里含 U+2028 字符**：按行读文件时只能按 `\n` 切分，不要用会把 U+2028 也当作换行的函数。
12. **href 写法有误**（例如无效的 IPv6 地址）：记录为 `invalid_href`，跳过即可，不要让整个流程中断。

---

## 7. 交付格式（务必严格按此格式，便于合并回总表）

提交一个 `results-remaining.json`，外加证据文件。

```json
{
  "generated_at": "2026-11-05T10:00:00Z",
  "executor": "公司 AI 名称 / 版本",
  "engine": {"name": "google-re2", "version": "1.1.x"},
  "entries": [
    {
      "entry_id": "S2-R109-E4",
      "task_ids": ["S2-R109-E4-T8-1", "S2-R109-E4-T10-2"],
      "entry_url": "https://www.coalchina.org.cn/list-20-1.html",
      "access": {"status": 200, "final_url": "…", "title": "…", "observed_at": "…",
                 "method": "浏览器 / 授权账号 / 无法访问", "note": "需人工通过验证 / 访问受限原因"},
      "scope": {
        "boundary_type": "path_prefix | page_name_parent | column_token | none",
        "boundary": "/insights/ 或 catid=20",
        "column_token": {"name": "catid", "value": "20", "other_values_seen": ["10", "16", "21"]},
        "evidence": "为什么这个边界能把本栏目和其他栏目区分开；页名退到上级时，附上 /x/ 专属本栏目的证据",
        "excluded_examples": [{"url": "…", "class": "C", "why": "同级栏目页 / 导航 / 站外 / 入口页本身"}]
      },
      "discovery_status": "完整 | 完整（列表+sitemap 合并枚举） | 完整（枚举结束，无独立全集对账） | 部分 | 未验证",
      "discovery_note": "翻了几页、加载更多点了几次、页面显示的总数与实际条数、sitemap 遍历情况、差额及原因",
      "rules": [
        {
          "rule_id": "S2-R109-E4-F1",
          "replaces": ["R3-S2-R109-E4-F1"],
          "pattern": "^https://…$",
          "status": "已验证 | 部分验证（候选） | 验证不通过",
          "target": "该规则覆盖什么（例如：本栏目文章详情页 / 本栏目列表分页页）",
          "variables": {"id": "[0-9]+ —— 依据：…"},
          "literals_column_token": ["catid=20"],
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
      "retained_links": [{"url": "…", "class": "B", "reason": "共享路径不带栏目标识 / 少于 4 个同结构 / 跳到家族外 / 文件 / 需登录"}],
      "redirects": [{"from": "…", "chain": [301, 200], "to": "…"}],
      "match_examples": ["已落地核验的正例 URL（标题，200，日期）"],
      "risks": ["快照时效、共享路径、需要人决定的范围问题等"]
    }
  ]
}
```

说明：

- `rule_id` 写成 `{entry_id}-F{序号}`。重做或替换旧规则的，在 `replaces` 里写上旧规则的 ID（旧 ID 见 `remaining-tasks.xlsx` 的“相关规则”列）。
- 一个入口没有任何 A 类对象时，`rules` 写成空数组，所有本栏目条目都放进 `retained_links`。这样的结果是**合法的交付**，不算失败。
- 旧规则如果经核实没有问题、不需要改，也要在 `rules` 里列出来，并在 `history` 里写明“复核通过、未修改”和复核的依据。

证据文件（每个站点一个文件夹，或者打包成 zip）：

- `visits.jsonl`：每次请求的时间、URL、每一跳的状态码、最终 URL 和标题；
- `links.jsonl`：第 3 步记录的全部链接，包括来源关系和 A、B、C 类别；
- `sitemaps/`：每个站点的 URL 清单，以及遍历摘要（读了哪些文件、哪些失败、是否完整）；
- `tests.json` 和 `re2-results.json`：每条规则的冻结样本和 RE2 运行结果；
- `identity.jsonl`：第 9 步中每个正例的落地核验结果。

---

## 8. 交付前自查清单

- [ ] 附录里的 208 个 `task_id` 都有对应的结论，一个不少；即使是“未验证”，也要列出来。
- [ ] 每个入口都写了 `scope`：边界是什么，凭什么能把本栏目和其他栏目区分开。
- [ ] **没有一条正则的边界是站点根 `/`**，也没有一条正则用变量覆盖栏目标识。
- [ ] 每条正则都不匹配入口页本身、同级栏目页、栏目标识取其他值的 URL，这些都已经作为反例实际测过。
- [ ] 共享路径和不带栏目标识的条目都放进了保留链接（B 类），没有被泛化。
- [ ] 每条“已验证”的规则都满足第 12 步的全部 8 项条件，并附有 RE2 版本和运行结果。
- [ ] 正则都以 `^` 开头、以 `$` 结尾，没有 `.*`、前瞻、后顾或反向引用，并且在 RE2 上编译通过。
- [ ] 没有为了通过测试而修改样本标签；v1 的留出样本在 v2 中只作为回归集使用。
- [ ] 所有正例都通过了落地核验；跳转到别处的和 404 的，都已剔除并记录原因。
- [ ] 每个入口的覆盖状态都写明了依据：翻了几页、点了几次、总数是多少、差额多少、原因是什么。
- [ ] 交付物里没有 Cookie、Token、账号或其他认证信息。
- [ ] 最后用一段话汇报，并且**分开计数**：
  - 完成了多少条任务；
  - 已验证的规则多少条、候选多少条；
  - 改为保留链接的多少条，替换旧规则多少条；
  - 访问受限多少个；
  - 主要缺口是什么。

---

## 附录：剩余任务逐条清单

完整字段（上一轮记录、相关规则的正则）见随附的 `remaining-tasks.xlsx`。同一入口可能有多条任务。

### T1 入口未打开（71 条）

要做什么：以正常身份打开（公司网络/授权账号/人工过验证），按完整流程第 1–13 步处理；仍打不开就写访问受限并附原因与时间

| task_id | 原表行 | 入口 URL | 上一轮记录（摘要） |
|---|---|---|---|
| S1-R3-E1-T1-1 | 第一批 3 | https://www.bls.gov/cex/ | 访问受限（站点 403，挑战页：Access Denied） |
| S1-R3-E2-T1-1 | 第一批 3 | https://www.bls.gov/news.release/cesan.htm | 访问受限（站点 403，挑战页：Access Denied） |
| S1-R42-E1-T1-1 | 第一批 42 | https://www.numerator.com/resources/ | 第 2 轮受阻项（见 round2/queue.json） |
| S1-R46-E1-T1-1 | 第一批 46 | https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights | 待核验（无站点状态码：ReadTimeout: HTTPSConnectionPool(host='www.mckinsey.com', port=443): Read timed ） |
| S1-R46-E2-T1-1 | 第一批 46 | https://www.mckinsey.com/capabilities/strategy-and-corporate-finance/our-insights | 待核验（无站点状态码：ReadTimeout: HTTPSConnectionPool(host='www.mckinsey.com', port=443): Read timed ） |
| S1-R46-E3-T1-1 | 第一批 46 | https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights/marketing-organization-and-operations | 待核验（无站点状态码：ReadTimeout: HTTPSConnectionPool(host='www.mckinsey.com', port=443): Read timed ） |
| S1-R47-E1-T1-1 | 第一批 47 | https://www.bcg.com/capabilities/marketing-sales/insights | 访问受限（站点 403，挑战页：Access Denied） |
| S1-R47-E2-T1-1 | 第一批 47 | https://www.bcg.com/capabilities/customer-insights/insights | 访问受限（站点 403，挑战页：Access Denied） |
| S1-R47-E3-T1-1 | 第一批 47 | https://www.bcg.com/industries/retail/insights | 访问受限（站点 403，挑战页：Access Denied） |
| S1-R47-E4-T1-1 | 第一批 47 | https://www.bcg.com/industries/consumer-products-industry/insights | 访问受限（站点 403，挑战页：Access Denied） |
| S1-R51-E1-T1-1 | 第一批 51 | https://www.gartner.com/en/marketing/insights | 访问受限（站点 403，挑战页：Just a moment... \| Gartner） |
| S1-R51-E2-T1-1 | 第一批 51 | https://www.gartner.com/en/sales/insights | 访问受限（站点 403，挑战页：Just a moment... \| Gartner） |
| S1-R51-E3-T1-1 | 第一批 51 | https://www.gartner.com/en/customer-service-support/insights | 访问受限（站点 403，挑战页：Just a moment... \| Gartner） |
| S1-R51-E4-T1-1 | 第一批 51 | https://www.gartner.com/en/finance/insights | 访问受限（站点 403，挑战页：Just a moment... \| Gartner） |
| S1-R51-E5-T1-1 | 第一批 51 | https://www.gartner.com/en/supply-chain | 访问受限（站点 403，挑战页：Just a moment... \| Gartner） |
| S1-R51-E6-T1-1 | 第一批 51 | https://www.gartner.com/en/insights/finance | 访问受限（站点 403，挑战页：Just a moment... \| Gartner） |
| S1-R63-E1-T1-1 | 第一批 63 | https://transparency.meta.com/policies/ | 访问受限（站点 400：Error） |
| S1-R81-E1-T1-1 | 第一批 81 | https://www.campaignlive.com/news | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R81-E2-T1-1 | 第一批 81 | https://www.campaignlive.com/in-depth | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R93-E1-T1-1 | 第一批 93 | https://lbbonline.com/work | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R93-E2-T1-1 | 第一批 93 | https://lbbonline.com/news | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R93-E3-T1-1 | 第一批 93 | https://lbbonline.com/reels | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R101-E1-T1-1 | 第一批 101 | https://searchengineland.com/library/guide | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R101-E2-T1-1 | 第一批 101 | https://searchengineland.com/guide | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R101-E3-T1-1 | 第一批 101 | https://searchengineland.com/library/guide/content-marketing-guide | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R101-E4-T1-1 | 第一批 101 | https://searchengineland.com/library/guide/ppc-guide | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R101-E5-T1-1 | 第一批 101 | https://searchengineland.com/library/guide/seo-guide | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R110-E1-T1-1 | 第一批 110 | https://www.vml.com/expertise/intelligence | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R110-E2-T1-1 | 第一批 110 | https://www.vml.com/insights | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R112-E1-T1-1 | 第一批 112 | https://www.adjust.com/resources/ | 访问受限（站点 429：Vercel Security Checkpoint） |
| S1-R112-E2-T1-1 | 第一批 112 | https://www.adjust.com/blog/ | 访问受限（站点 429：Vercel Security Checkpoint） |
| S1-R143-E1-T1-1 | 第一批 143 | https://business.adobe.com/resources/reports.html | 待核验（无站点状态码：ReadTimeout: HTTPSConnectionPool(host='business.adobe.com', port=443): Read time） |
| S1-R143-E2-T1-1 | 第一批 143 | https://business.adobe.com/resources/digital-trends-research-center.html | 待核验（无站点状态码：ReadTimeout: HTTPSConnectionPool(host='business.adobe.com', port=443): Read time） |
| S1-R143-E3-T1-1 | 第一批 143 | https://business.adobe.com/resources/adobe-digital-insights.html | 待核验（无站点状态码：ReadTimeout: HTTPSConnectionPool(host='business.adobe.com', port=443): Read time） |
| S1-R144-E1-T1-1 | 第一批 144 | https://www.crunchbase.com/discover/organization.companies | 访问受限（站点 403，挑战页：Attention Required! \| Cloudflare） |
| S1-R145-E1-T1-1 | 第一批 145 | https://pitchbook.com/news | 访问受限（站点 403，挑战页：Just a moment...） |
| S1-R152-E2-T1-1 | 第一批 152 | https://dealroom.co/reports | 访问受限（站点 403，挑战页：Attention Required! \| Cloudflare） |
| S1-R152-E3-T1-1 | 第一批 152 | https://dealroom.co/resources | 访问受限（站点 403，挑战页：Attention Required! \| Cloudflare） |
| S1-R152-E4-T1-1 | 第一批 152 | https://dealroom.co/news/ | 访问受限（站点 403，挑战页：Attention Required! \| Cloudflare） |
| S1-R152-E5-T1-1 | 第一批 152 | https://dealroom.co/companies/ | 访问受限（站点 403，挑战页：Attention Required! \| Cloudflare） |
| S1-R152-E6-T1-1 | 第一批 152 | https://dealroom.co/investors/ | 访问受限（站点 403，挑战页：Attention Required! \| Cloudflare） |
| S1-R152-E7-T1-1 | 第一批 152 | https://dealroom.co/market-maps/ | 访问受限（站点 403，挑战页：Attention Required! \| Cloudflare） |
| S1-R152-E8-T1-1 | 第一批 152 | https://dealroom.co/power-law-outcomes/ | 访问受限（站点 403，挑战页：Attention Required! \| Cloudflare） |
| S1-R152-E9-T1-1 | 第一批 152 | https://dealroom.co/talent/founder-mafias/ | 访问受限（站点 403，挑战页：Attention Required! \| Cloudflare） |
| S1-R152-E10-T1-1 | 第一批 152 | https://dealroom.co/tech-macro-economics/ | 访问受限（站点 403，挑战页：Attention Required! \| Cloudflare） |
| S1-R152-E11-T1-1 | 第一批 152 | https://dealroom.co/vc-investment-dashboard/ | 访问受限（站点 403，挑战页：Attention Required! \| Cloudflare） |
| S2-R24-E1-T1-1 | 第二批 24 | https://www.csm.com.cn/yjdc/Index.html | 待核验（无站点状态码：ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection r） |
| S2-R29-E1-T1-1 | 第二批 29 | https://www.datastory.com.cn/analyst | 待核验（无站点状态码：未请求） |
| S2-R29-E2-T1-1 | 第二批 29 | https://www.datastory.com.cn/case | 待核验（无站点状态码：未请求） |
| S2-R29-E3-T1-1 | 第二批 29 | https://www.datastory.com.cn/analyst/report.html | 待核验（无站点状态码：未请求） |
| S2-R29-E4-T1-1 | 第二批 29 | https://www.datastory.com.cn/analyst/hotspot.html | 待核验（无站点状态码：未请求） |
| S2-R43-E1-T1-1 | 第二批 43 | http://syntun.com.cn/datanews/hotspot.html | 访问受限（站点 403：403 Forbidden） |
| S2-R46-E1-T1-1 | 第二批 46 | https://www.iyiou.com/svip | 待核验（无站点状态码：未请求） |
| S2-R50-E1-T1-1 | 第二批 50 | https://www.vzkoo.com/question | 访问受限（站点 403：） |
| S2-R71-E1-T1-1 | 第二批 71 | https://www.digitaling.com/moments | 访问受限（站点 403：403 Forbidden） |
| S2-R86-E1-T1-1 | 第二批 86 | http://www.linkshop.com/news/ | 待核验（无站点状态码：未请求） |
| S2-R86-E2-T1-1 | 第二批 86 | http://www.linkshop.com/data/cb/ | 待核验（无站点状态码：未请求） |
| S2-R86-E3-T1-1 | 第二批 86 | http://www.linkshop.com/column/ | 待核验（无站点状态码：未请求） |
| S2-R86-E4-T1-1 | 第二批 86 | http://www.linkshop.com/interview/rw/ | 待核验（无站点状态码：未请求） |
| S2-R86-E5-T1-1 | 第二批 86 | http://www.linkshop.com/data/hy/ | 待核验（无站点状态码：未请求） |
| S2-R86-E6-T1-1 | 第二批 86 | http://www.linkshop.com/data/sl/ | 待核验（无站点状态码：未请求） |
| S2-R86-E7-T1-1 | 第二批 86 | http://www.linkshop.com/interview/xd/ | 待核验（无站点状态码：未请求） |
| S2-R86-E8-T1-1 | 第二批 86 | http://www.linkshop.com/interview/mq/ | 待核验（无站点状态码：未请求） |
| S2-R86-E9-T1-1 | 第二批 86 | http://www.linkshop.com/case/ | 待核验（无站点状态码：未请求） |
| S2-R86-E10-T1-1 | 第二批 86 | http://www.linkshop.com/pdl/ | 待核验（无站点状态码：未请求） |
| S2-R105-E1-T1-1 | 第二批 105 | https://www.chinapv.org.cn/StaticPage/Building/list50_1.html | 待核验（无站点状态码：SSLError: HTTPSConnectionPool(host='www.chinapv.org.cn', port=443): Max retries ） |
| S2-R114-E1-T1-1 | 第二批 114 | https://www.weiboyi.com/report | 待核验（无站点状态码：ProxyError: HTTPSConnectionPool(host='www.weiboyi.com', port=443): Max retries e） |
| S2-R114-E2-T1-1 | 第二批 114 | https://www.weiboyi.com/meeting | 待核验（无站点状态码：ProxyError: HTTPSConnectionPool(host='www.weiboyi.com', port=443): Max retries e） |
| S2-R124-E3-T1-1 | 第二批 124 | https://www.huiju.cool/industryinsight/ | 访问受限（站点 403：403 Forbidden） |
| S2-R134-E1-T1-1 | 第二批 134 | https://www.qixin.com/pay/vip | 待核验（无站点状态码：未请求） |
| S2-R134-E2-T1-1 | 第二批 134 | https://www.qixin.com/app-center/ | 待核验（无站点状态码：未请求） |

### T2 无标准链接（脚本渲染）（13 条）

要做什么：浏览器打开，用开发者工具 Network 看页面自己的只读数据请求，或逐个点击卡片记录落地 URL；按第 1 节判定每个落地 URL 属于 A/B/C

| task_id | 原表行 | 入口 URL | 上一轮记录（摘要） |
|---|---|---|---|
| S1-R34-E1-T2-1 | 第一批 34 | https://www.circana.com/insights | 部分：静态请求 1 页（入口+分页），未完成分页 0；浏览器渲染 2 轮、点击加载更多 0 次、渲染后链接 8；前缀 /insights/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚 |
| S2-R26-E2-T2-1 | 第二批 26 | https://www.leadleo.com/report/search | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /report/search/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚本组件渲染 |
| S2-R39-E1-T2-1 | 第二批 39 | https://www.yanbaoke.com/openclaw | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /openclaw/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚本组件渲染 |
| S2-R39-E2-T2-1 | 第二批 39 | https://www.yanbaoke.com/ai-searches | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /ai-searches/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚本组件渲染 |
| S2-R57-E2-T2-1 | 第二批 57 | https://e.xiaohongshu.com/numerous | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /numerous/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚本组件渲染 |
| S2-R65-E1-T2-1 | 第二批 65 | https://creator.douyin.com/creator-micro/creator-count/arithmetic-index | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /creator-micro/creator-count/arithmetic-index/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]） |
| S2-R66-E1-T2-1 | 第二批 66 | https://survey.jd.com/page/ecological | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /page/ecological/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚本组件渲染 |
| S2-R66-E2-T2-1 | 第二批 66 | https://survey.jd.com/page/edition | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /page/edition/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚本组件渲染 |
| S2-R87-E1-T2-1 | 第二批 87 | https://www.woshipm.com/harmony | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /harmony/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚本组件渲染 |
| S2-R119-E10-T2-1 | 第二批 119 | https://www.focusmedia.cn/publication#jump | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /publication/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚本组件渲染 |
| S2-R140-E1-T2-1 | 第二批 140 | https://www.mob.com/mobdata/report | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /mobdata/report/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚本组件渲染 |
| S2-R144-E1-T2-1 | 第二批 144 | https://e.newrank.cn/marketing/IndustryInformation | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /marketing/IndustryInformation/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚本组件渲染 |
| S2-R144-E2-T2-1 | 第二批 144 | https://geo.newrank.cn/news | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /news/ 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）；页面上没有可枚举的标准链接（a[href]），内容可能由脚本组件渲染 |

### T3 边界内无下级家族（21 条）

要做什么：重判栏目边界（第 1.3 节，特别是“列表页名”形式的末段）；条目在边界外且无法证明专属本栏目时，作为 B 类保留链接（精确清单），不写正则

| task_id | 原表行 | 入口 URL | 上一轮记录（摘要） |
|---|---|---|---|
| S2-R15-E2-T3-1 | 第二批 15 | https://www.ctrchina.cn/report | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /report/ 下家族 0 个、成员 0；前缀外同站链接 6、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R26-E1-T3-1 | 第二批 26 | https://www.leadleo.com/wiki/topicList | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /wiki/topicList/ 下家族 0 个、成员 0；前缀外同站链接 5、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R26-E3-T3-1 | 第二批 26 | https://www.leadleo.com/wiki/getLeadleoIndustryCatelogue | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /wiki/getLeadleoIndustryCatelogue/ 下家族 0 个、成员 0；前缀外同站链接 1、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R26-E4-T3-1 | 第二批 26 | https://www.leadleo.com/video/allType | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /video/allType/ 下家族 0 个、成员 0；前缀外同站链接 5、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R26-E5-T3-1 | 第二批 26 | https://www.leadleo.com/article/search | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /article/search/ 下家族 0 个、成员 0；前缀外同站链接 5、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R44-E2-T3-1 | 第二批 44 | https://www.frostchina.com/content/whitepaper-store?page=1 | 部分：静态请求 38 页（入口+分页），未完成分页 16；前缀 /content/whitepaper-store/ 下家族 0 个、成员 0；前缀外同站链接 56、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R60-E1-T3-1 | 第二批 60 | https://jzt.jd.com/school/index | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /school/index/ 下家族 0 个、成员 0；前缀外同站链接 117、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R63-E1-T3-1 | 第二批 63 | https://qn.taobao.com/headline/news | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 / 下家族 0 个、成员 0；前缀外同站链接 2、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R63-E2-T3-1 | 第二批 63 | https://qn.taobao.com/headline/course | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 / 下家族 0 个、成员 0；前缀外同站链接 2、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R65-E2-T3-1 | 第二批 65 | https://creator.douyin.com/creator-micro/creator-count/vertical-analysis | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /creator-micro/creator-count/vertical-analysis/ 下家族 0 个、成员 0；前缀外同站链接 7、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R65-E3-T3-1 | 第二批 65 | https://creator.douyin.com/creator-micro/creator-count/arithmetic-report | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /creator-micro/creator-count/arithmetic-report/ 下家族 0 个、成员 0；前缀外同站链接 7、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R79-E4-T3-1 | 第二批 79 | https://www.morketing.com/ecosystem | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /ecosystem/ 下家族 0 个、成员 0；前缀外同站链接 4、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R92-E2-T3-1 | 第二批 92 | https://www.topys.cn/branding | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /branding/ 下家族 0 个、成员 0；前缀外同站链接 19、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R113-E1-T3-1 | 第二批 113 | https://www.chanmama.com/douyin/ | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /douyin/ 下家族 0 个、成员 0；前缀外同站链接 60、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R113-E2-T3-1 | 第二批 113 | https://cy.chanmama.com/insights | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /insights/ 下家族 0 个、成员 0；前缀外同站链接 2、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R119-E1-T3-1 | 第二批 119 | https://www.focusmedia.cn/classic | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /classic/ 下家族 0 个、成员 0；前缀外同站链接 15、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R119-E2-T3-1 | 第二批 119 | https://www.focusmedia.cn/entrepreneurship | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /entrepreneurship/ 下家族 0 个、成员 0；前缀外同站链接 14、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R119-E3-T3-1 | 第二批 119 | https://www.focusmedia.cn/industry | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /industry/ 下家族 0 个、成员 0；前缀外同站链接 15、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R119-E5-T3-1 | 第二批 119 | https://www.focusmedia.cn/whitepaper | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /whitepaper/ 下家族 0 个、成员 0；前缀外同站链接 5、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R124-E1-T3-1 | 第二批 124 | https://a.huiju.cool/service/extcontent/page/f5cdd968712448afa6f2d1953590b3fc/home/1061 | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /service/extcontent/page/f5cdd968712448afa6f2d1953590b3fc/home/1061/ 下家族 0 个、成员 0；前缀外同站链接 1、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |
| S2-R126-E1-T3-1 | 第二批 126 | https://www.sensorsdata.cn/target_disassembly.html | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 / 下家族 0 个、成员 0；前缀外同站链接 0、文件 0；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外） |

### T4 列表未枚举到底（8 条）

要做什么：在浏览器里翻页 / 点加载更多直到到底（按钮消失或连续 3 次无新内容），核对页面显示的总数；再按第 5–12 步重新归纳与验证

| task_id | 原表行 | 入口 URL | 上一轮记录（摘要） |
|---|---|---|---|
| S2-R16-E1-T4-1 | 第二批 16 | https://www.cbndata.com/report | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /report/ 下家族 1 个、成员 250；前缀外同站链接 83、文件 0；sitemap 中同结构但不在列表的 URL：F1=0；浏览器渲染只取到首屏或前几屏，未确认到底 |
| S2-R20-E1-T4-1 | 第二批 20 | https://www.feigua.cn/StudyReport | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /StudyReport/ 下家族 1 个、成员 24；前缀外同站链接 7、文件 0；sitemap 中同结构但不在列表的 URL：F1=0；浏览器渲染只取到首屏或前几屏，未确认到底 |
| S2-R60-E3-T4-1 | 第二批 60 | https://jzt.jd.com/gw/information | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /gw/information/ 下家族 1 个、成员 8；前缀外同站链接 31、文件 0；sitemap 中同结构但不在列表的 URL：F1=0；浏览器渲染只取到首屏或前几屏，未确认到底 |
| S2-R79-E2-T4-1 | 第二批 79 | https://www.morketing.com/newsflash | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /newsflash/ 下家族 1 个、成员 10；前缀外同站链接 10、文件 0；sitemap 中同结构但不在列表的 URL：F1=0；浏览器渲染只取到首屏或前几屏，未确认到底 |
| S2-R79-E3-T4-1 | 第二批 79 | https://www.morketing.com/columns | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /columns/ 下家族 1 个、成员 12；前缀外同站链接 4、文件 0；sitemap 中同结构但不在列表的 URL：F1=0；浏览器渲染只取到首屏或前几屏，未确认到底 |
| S2-R87-E2-T4-1 | 第二批 87 | https://www.woshipm.com/fish/ | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /fish/ 下家族 1 个、成员 7；前缀外同站链接 215、文件 0；sitemap 中同结构但不在列表的 URL：F1=0；浏览器渲染只取到首屏或前几屏，未确认到底 |
| S2-R112-E1-T4-1 | 第二批 112 | https://www.iresearch.com.cn/Research.shtml | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /Research/ 下家族 1 个、成员 6；前缀外同站链接 12、文件 0；sitemap 中同结构但不在列表的 URL：F1=0；浏览器渲染只取到首屏或前几屏，未确认到底 |
| S2-R144-E3-T4-1 | 第二批 144 | https://a.newrank.cn/trade/news/ | 部分：静态请求 1 页（入口+分页），未完成分页 0；前缀 /trade/news/ 下家族 2 个、成员 45；前缀外同站链接 6、文件 0；sitemap 中同结构但不在列表的 URL：F1=0、F2=0；内容区无前缀内链接，栏目条目取自页面 nav/header 中的前缀内链接；浏览器渲染只取到首屏或前几屏，未确 |

### T5 Hash 路由翻页未枚举（7 条）

要做什么：在浏览器里翻完该 Hash 路由列表（翻页 / 加载更多 / 滚动），点击取得更多落地 URL，每个都单独打开核验身份；补齐变量取值后重新验证

| task_id | 原表行 | 入口 URL | 上一轮记录（摘要） |
|---|---|---|---|
| S2-R56-E1-T5-1 | 第二批 56 | https://e.kuaishou.com/#/e/news | 部分：Hash 路由入口，HTTP 只能取到同一外壳；浏览器点击首屏卡片取得 8 个同家族落地地址（另 0 个落到家族外），列表的翻页/加载更多未枚举 |
| S2-R56-E2-T5-1 | 第二批 56 | https://e.kuaishou.com/#/e/report | 部分：Hash 路由入口，HTTP 只能取到同一外壳；浏览器点击首屏卡片取得 8 个同家族落地地址（另 0 个落到家族外），列表的翻页/加载更多未枚举 |
| S2-R56-E3-T5-1 | 第二批 56 | https://e.kuaishou.com/#/e/cases | 部分：Hash 路由入口，HTTP 只能取到同一外壳；浏览器点击首屏卡片取得 6 个同家族落地地址（另 1 个落到家族外），列表的翻页/加载更多未枚举 |
| S2-R58-E1-T5-1 | 第二批 58 | https://www.alimama.com/index.htm#!/marketing-case/index | 部分：Hash 路由入口，HTTP 只能取到同一外壳；浏览器点击首屏卡片取得 8 个同家族落地地址（另 0 个落到家族外），列表的翻页/加载更多未枚举 |
| S2-R58-E2-T5-1 | 第二批 58 | https://www.alimama.com/index.htm#!/marketing-insight/index | 部分：Hash 路由入口，HTTP 只能取到同一外壳；浏览器点击首屏卡片取得 8 个同家族落地地址（另 0 个落到家族外），列表的翻页/加载更多未枚举 |
| S2-R58-E3-T5-1 | 第二批 58 | https://www.alimama.com/index.htm#!/marketing-wiki/index | 部分：Hash 路由入口，HTTP 只能取到同一外壳；浏览器点击首屏卡片取得 6 个同家族落地地址（另 1 个落到家族外），列表的翻页/加载更多未枚举 |
| S2-R138-E1-T5-1 | 第二批 138 | https://learn.incopat.com/#/ | 部分：Hash 路由入口，HTTP 只能取到同一外壳；浏览器点击首屏卡片取得 8 个同家族落地地址（另 0 个落到家族外），列表的翻页/加载更多未枚举 |

### T6 分页未翻完（5 条）

要做什么：从上一轮停下的位置继续翻页直到最后一页，对账总数；补入成员后重跑覆盖检查

| task_id | 原表行 | 入口 URL | 上一轮记录（摘要） |
|---|---|---|---|
| S2-R44-E2-T6-2 | 第二批 44 | https://www.frostchina.com/content/whitepaper-store?page=1 | 继续分页 16 个待访问页 |
| S2-R74-E1-T6-1 | 第二批 74 | https://www.growthhk.cn/cgo | 继续分页 1 个待访问页 |
| S2-R74-E2-T6-1 | 第二批 74 | https://www.growthhk.cn/quan | 继续分页 3 个待访问页 |
| S2-R84-E1-T6-1 | 第二批 84 | https://www.foodaily.com/articles | 继续分页 2 个待访问页 |
| S2-R84-E2-T6-1 | 第二批 84 | https://www.foodaily.com/newsflashes | 继续分页 2 个待访问页 |

### T7 sitemap 对账缺口（10 条）

要做什么：逐个判断 sitemap 中多出来的同结构 URL 是否属于本栏目（打开看面包屑 / 栏目标签 / 是否出现在列表的后续页）；属于的补进覆盖，不属于的说明原因

| task_id | 原表行 | 入口 URL | 上一轮记录（摘要） |
|---|---|---|---|
| S2-R20-E3-T7-1 | 第二批 20 | https://ks.feigua.cn/news/ | R3-S2-R20-E3-F1：sitemap 有 61 个同结构 URL 不在列表中，确认是否为本栏目成员/列表未展示 |
| S2-R20-E3-T7-2 | 第二批 20 | https://ks.feigua.cn/news/ | R3-S2-R20-E3-F2：sitemap 有 2 个同结构 URL 不在列表中，确认是否为本栏目成员/列表未展示 |
| S2-R20-E3-T7-4 | 第二批 20 | https://ks.feigua.cn/news/ | R3-S2-R20-E3-F3：sitemap 有 14 个同结构 URL 不在列表中，确认是否为本栏目成员/列表未展示 |
| S2-R74-E1-T7-2 | 第二批 74 | https://www.growthhk.cn/cgo | R3-S2-R74-E1-F1：sitemap 有 4205 个同结构 URL 不在列表中，确认是否为本栏目成员/列表未展示 |
| S2-R74-E1-T7-3 | 第二批 74 | https://www.growthhk.cn/cgo | R3-S2-R74-E1-F2：sitemap 有 676 个同结构 URL 不在列表中，确认是否为本栏目成员/列表未展示 |
| S2-R74-E2-T7-2 | 第二批 74 | https://www.growthhk.cn/quan | R3-S2-R74-E2-F1：sitemap 有 5488 个同结构 URL 不在列表中，确认是否为本栏目成员/列表未展示 |
| S2-R126-E2-T7-1 | 第二批 126 | https://www.sensorsdata.cn/school/library | R3-S2-R126-E2-F1：sitemap 有 39 个同结构 URL 不在列表中，确认是否为本栏目成员/列表未展示 |
| S2-R126-E3-T7-1 | 第二批 126 | https://www.sensorsdata.cn/blog | R3-S2-R126-E3-F1：sitemap 有 13 个同结构 URL 不在列表中，确认是否为本栏目成员/列表未展示 |
| S2-R126-E3-T7-2 | 第二批 126 | https://www.sensorsdata.cn/blog | R3-S2-R126-E3-F2：sitemap 有 10 个同结构 URL 不在列表中，确认是否为本栏目成员/列表未展示 |
| S2-R126-E3-T7-4 | 第二批 126 | https://www.sensorsdata.cn/blog | R3-S2-R126-E3-F3：sitemap 有 10 个同结构 URL 不在列表中，确认是否为本栏目成员/列表未展示 |

### T8 规则未达准入（候选）（24 条）

要做什么：补齐缺的准入条件（见“上一轮记录”）：找独立留出样本、补落地核验、去重；补不齐就保持候选并写明缺什么

| task_id | 原表行 | 入口 URL | 上一轮记录（摘要） |
|---|---|---|---|
| S1-R18-E4-T8-1 | 第一批 18 | https://www.itu.int/en/action/Pages/default.aspx | R3-S1-R18-E4-F2：机械门未通过：无独立留出正例（sitemap、后续分页、其他页面、详情页链接均无同结构样本） |
| S1-R19-E4-T8-1 | 第一批 19 | https://www.wipo.int/en/web/patentscope/ | R3-S1-R19-E4-F1：机械门未通过：归纳正例 2<3 |
| S1-R19-E12-T8-1 | 第一批 19 | https://www.wipo.int/en/web/business | R3-S1-R19-E12-F1：机械门未通过：留出与归纳/回归重叠；列表成员漏配 1 |
| S1-R27-E1-T8-1 | 第一批 27 | https://www.euromonitor.com/articles | R3-S1-R27-E1-F2：机械门未通过：留出与归纳/回归重叠 |
| S1-R35-E1-T8-1 | 第一批 35 | https://www.comscore.com/Insights/Blog | R3-S1-R35-E1-F1：机械门未通过：留出与归纳/回归重叠 |
| S1-R86-E1-T8-1 | 第一批 86 | https://www.dandad.org/work/annual-2026/ | R3-S1-R86-E1-F2：机械门未通过：无独立留出正例（sitemap、后续分页、其他页面、详情页链接均无同结构样本） |
| S1-R91-E1-T8-1 | 第一批 91 | https://growthhackers.com/growth-studies/ | R3-S1-R91-E1-F1：机械门未通过：无独立留出正例（sitemap、后续分页、其他页面、详情页链接均无同结构样本） |
| S1-R133-E1-T8-1 | 第一批 133 | https://www.siegelgale.com/ideas/ | R3-S1-R133-E1-F1：机械门未通过：无独立留出正例（sitemap、后续分页、其他页面、详情页链接均无同结构样本） |
| S2-R15-E1-T8-1 | 第二批 15 | www.ctrchina.cn/product/MI | R3-S2-R15-E1-F1：机械门未通过：有正例未完成落地身份核验 |
| S2-R20-E2-T8-1 | 第二批 20 | https://dy.feigua.cn/Article2/ | R3-S2-R20-E2-F1：机械门未通过：样本重复 |
| S2-R20-E3-T8-3 | 第二批 20 | https://ks.feigua.cn/news/ | R3-S2-R20-E3-F2：机械门未通过：无独立留出正例（sitemap、后续分页、其他页面、详情页链接均无同结构样本） |
| S2-R20-E3-T8-5 | 第二批 20 | https://ks.feigua.cn/news/ | R3-S2-R20-E3-F3：机械门未通过：留出与归纳/回归重叠 |
| S2-R27-E2-T8-1 | 第二批 27 | https://bg.qianzhan.com/report/ | R3-S2-R27-E2-F1：机械门未通过：有正例未完成落地身份核验 |
| S2-R27-E2-T8-2 | 第二批 27 | https://bg.qianzhan.com/report/ | R3-S2-R27-E2-F2：机械门未通过：留出反例 2<3、留出与归纳/回归重叠 |
| S2-R57-E1-T8-1 | 第二批 57 | https://e.xiaohongshu.com/case | R3-S2-R57-E1-F1：机械门未通过：留出反例 1<3 |
| S2-R58-E3-T8-2 | 第二批 58 | https://www.alimama.com/index.htm#!/marketing-wiki/index | R3H-S2-R58-E3-F1：skey 只观察到 popularization 一个取值，而页面上还有其他子分类（已观察到 skeys=answer），很可能漏配其他子分类 |
| S2-R107-E1-T8-1 | 第二批 107 | https://www.cntac.org.cn/zixun/ | R3-S2-R107-E1-F2：机械门未通过：样本重复 |
| S2-R109-E4-T8-1 | 第二批 109 | https://www.coalchina.org.cn/list-20-1.html | R3-S2-R109-E4-F2：机械门未通过：无独立留出正例（sitemap、后续分页、其他页面、详情页链接均无同结构样本） |
| S2-R109-E10-T8-1 | 第二批 109 | https://www.coalchina.org.cn/list-41-1.html | R3-S2-R109-E10-F2：机械门未通过：样本重复 |
| S2-R109-E13-T8-1 | 第二批 109 | http://www.coalchina.org.cn/list-42-1.html | R3-S2-R109-E13-F2：机械门未通过：无独立留出正例（sitemap、后续分页、其他页面、详情页链接均无同结构样本） |
| S2-R117-E2-T8-1 | 第二批 117 | https://www.talkingdata.com/insights.jsp?languagetype=zh_cn#industry-news | R3-S2-R117-E2-F1：机械门未通过：留出反例 2<3 |
| S2-R126-E3-T8-3 | 第二批 126 | https://www.sensorsdata.cn/blog | R3-S2-R126-E3-F2：机械门未通过：留出与归纳/回归重叠 |
| S2-R145-E1-T8-1 | 第二批 145 | https://www.kolkoc.com/news/ | R3-S2-R145-E1-F1：机械门未通过：样本重复 |
| S2-R145-E1-T8-2 | 第二批 145 | https://www.kolkoc.com/news/ | R3-S2-R145-E1-F2：机械门未通过：样本重复 |

### T9 规则验证不通过（同级栏目）（10 条）

要做什么：这类规则匹配到了同级栏目页（C 类）。不要放宽或改标签：改为保留链接，或找到本栏目专属的标识后重写

| task_id | 原表行 | 入口 URL | 上一轮记录（摘要） |
|---|---|---|---|
| S2-R82-E2-T9-1 | 第二批 82 | https://www.jiemian.com/lists/800.html | R3-S2-R82-E2-F1：机械门未通过：标注测试有失败（留出 FN1/FP1）、留出指标 <95% |
| S2-R82-E11-T9-1 | 第二批 82 | https://www.jiemian.com/lists/51.html | R3-S2-R82-E11-F1：机械门未通过：标注测试有失败（留出 FN1/FP1）、留出指标 <95% |
| S2-R82-E13-T9-1 | 第二批 82 | https://www.jiemian.com/lists/30.html | R3-S2-R82-E13-F1：机械门未通过：标注测试有失败（留出 FN1/FP1）、留出指标 <95% |
| S2-R108-E2-T9-1 | 第二批 108 | https://www.cheaa.org/channels/13.html | R3-S2-R108-E2-F1：机械门未通过：标注测试有失败（留出 FN4/FP1）、留出指标 <95% |
| S2-R108-E3-T9-1 | 第二批 108 | https://www.cheaa.org/channels/14.html | R3-S2-R108-E3-F1：机械门未通过：标注测试有失败（留出 FN3/FP1）、留出指标 <95% |
| S2-R108-E10-T9-1 | 第二批 108 | https://www.cheaa.org/channels/420.html | R3-S2-R108-E10-F1：机械门未通过：标注测试有失败（留出 FN5/FP1）、留出指标 <95% |
| S2-R108-E16-T9-1 | 第二批 108 | https://www.cheaa.org/channels/33.html | R3-S2-R108-E16-F1：机械门未通过：标注测试有失败（留出 FN4/FP1）、留出指标 <95% |
| S2-R108-E19-T9-1 | 第二批 108 | https://www.cheaa.org/channels/492.html | R3-S2-R108-E19-F1：机械门未通过：标注测试有失败（留出 FN3/FP1）、留出指标 <95% |
| S2-R108-E21-T9-1 | 第二批 108 | https://www.cheaa.org/channels/600.html | R3-S2-R108-E21-F1：机械门未通过：标注测试有失败（留出 FN5/FP1）、留出指标 <95% |
| S2-R108-E22-T9-1 | 第二批 108 | https://www.cheaa.org/channels/635.html | R3-S2-R108-E22-F1：机械门未通过：标注测试有失败（留出 FN5/FP1）、留出指标 <95% |

### T10 已交付规则范围超界（39 条）

要做什么：按第 1.3 节重新确定栏目标识：详情 URL 带本栏目标识（如 catid=20）时把它写成字面量；不带时改为 B 类保留链接；重新验证后替换原规则

| task_id | 原表行 | 入口 URL | 上一轮记录（摘要） |
|---|---|---|---|
| S2-R47-E1-T10-1 | 第二批 47 | https://www.jazzyear.com/study_list.html | R3-S2-R47-E1-F1：边界退化为站点根 /，正则 ^https://www\.jazzyear\.com/study_info\.html\?id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R47-E3-T10-1 | 第二批 47 | https://www.jazzyear.com/article_list.html?type=1 | R3-S2-R47-E3-F1：边界退化为站点根 /，正则 ^https://www\.jazzyear\.com/article_info\.html\?id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R47-E3-T10-2 | 第二批 47 | https://www.jazzyear.com/article_list.html?type=1 | R3-S2-R47-E3-F2：边界退化为站点根 /，正则 ^https://www\.jazzyear\.com/[a-z_]+\.html$ 会匹配其他栏目的页面 |
| S2-R47-E4-T10-1 | 第二批 47 | https://www.jazzyear.com/article_list.html?type=2 | R3-S2-R47-E4-F1：边界退化为站点根 /，正则 ^https://www\.jazzyear\.com/article_info\.html\?id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R47-E4-T10-2 | 第二批 47 | https://www.jazzyear.com/article_list.html?type=2 | R3-S2-R47-E4-F2：边界退化为站点根 /，正则 ^https://www\.jazzyear\.com/[a-z_]+\.html$ 会匹配其他栏目的页面 |
| S2-R47-E5-T10-1 | 第二批 47 | https://www.jazzyear.com/article_list.html?type=3 | R3-S2-R47-E5-F1：边界退化为站点根 /，正则 ^https://www\.jazzyear\.com/article_info\.html\?id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R47-E5-T10-2 | 第二批 47 | https://www.jazzyear.com/article_list.html?type=3 | R3-S2-R47-E5-F2：边界退化为站点根 /，正则 ^https://www\.jazzyear\.com/[a-z_]+\.html$ 会匹配其他栏目的页面 |
| S2-R47-E6-T10-1 | 第二批 47 | https://www.jazzyear.com/article_list.html?type=4 | R3-S2-R47-E6-F1：边界退化为站点根 /，正则 ^https://www\.jazzyear\.com/article_info\.html\?id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R47-E6-T10-2 | 第二批 47 | https://www.jazzyear.com/article_list.html?type=4 | R3-S2-R47-E6-F2：边界退化为站点根 /，正则 ^https://www\.jazzyear\.com/[a-z_]+\.html$ 会匹配其他栏目的页面 |
| S2-R47-E7-T10-1 | 第二批 47 | https://www.jazzyear.com/article_list.html?type=6 | R3-S2-R47-E7-F1：边界退化为站点根 /，正则 ^https://www\.jazzyear\.com/[a-z_]+\.html$ 会匹配其他栏目的页面 |
| S2-R93-E2-T10-1 | 第二批 93 | https://www.chinaventure.com.cn/index.html | R3-S2-R93-E2-F1：边界退化为站点根 /，正则 ^https://www\.chinaventure\.com\.cn/[a-z]+/[a-z0-9_-]+\.html$ 会匹配其他栏目的页面 |
| S2-R109-E1-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-10-1.html | R3-S2-R109-E1-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E1-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-10-1.html | R3-S2-R109-E1-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E2-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-16-1.html | R3-S2-R109-E2-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E2-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-16-1.html | R3-S2-R109-E2-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E3-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-12-1.html | R3-S2-R109-E3-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E3-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-12-1.html | R3-S2-R109-E3-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E4-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-20-1.html | R3-S2-R109-E4-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E5-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-25-1.html | R3-S2-R109-E5-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E5-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-25-1.html | R3-S2-R109-E5-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E6-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-67-1.html | R3-S2-R109-E6-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E6-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-67-1.html | R3-S2-R109-E6-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E7-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-39-1.html | R3-S2-R109-E7-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E7-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-39-1.html | R3-S2-R109-E7-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E8-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-407-1.html | R3-S2-R109-E8-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E9-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-44-1.html | R3-S2-R109-E9-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E9-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-44-1.html | R3-S2-R109-E9-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E10-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-41-1.html | R3-S2-R109-E10-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E11-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-45-1.html | R3-S2-R109-E11-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E11-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-45-1.html | R3-S2-R109-E11-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E12-T10-1 | 第二批 109 | http://www.coalchina.org.cn/list-43-1.html | R3-S2-R109-E12-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E12-T10-2 | 第二批 109 | http://www.coalchina.org.cn/list-43-1.html | R3-S2-R109-E12-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E13-T10-2 | 第二批 109 | http://www.coalchina.org.cn/list-42-1.html | R3-S2-R109-E13-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E14-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-40-1.html | R3-S2-R109-E14-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E14-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-40-1.html | R3-S2-R109-E14-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E15-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-72-1.html | R3-S2-R109-E15-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E15-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-72-1.html | R3-S2-R109-E15-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E16-T10-1 | 第二批 109 | https://www.coalchina.org.cn/list-82-1.html | R3-S2-R109-E16-F1：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=lists&catid=[0-9]*$ 会匹配其他栏目的页面 |
| S2-R109-E16-T10-2 | 第二批 109 | https://www.coalchina.org.cn/list-82-1.html | R3-S2-R109-E16-F2：边界退化为站点根 /，正则 ^https://www\.coalchina\.org\.cn/index\.php\?m=content&c=index&a=show&catid=[0-9]*&id=[0-9]*$ 会匹配其他栏目的页面 |
