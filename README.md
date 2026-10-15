# AI × 科研效率周报

每周三早上 8:00（北京时间），自动把这一周 AI 圈里**真正能帮你做科研**的东西，
整理成一封中文邮件发到你的邮箱。

选题范围覆盖科研全流程：文献检索、文献阅读、文献筛选、生信分析、统计绘图、
论文写作、投稿合规、以及能让这些环节更快的新工具和新技能。

---

## 你会收到什么

每封邮件固定长这样：

| 板块 | 内容 |
| --- | --- |
| 顶部导读 | 一句话概括这周最值得注意的信号 |
| 🎯 本周只值得动手试的一件事 | 全场最高分的那一条，附上"为什么是它" |
| 🔧 工具雷达 | 能直接下载/注册就用的软件、网站、插件 |
| 🧪 方法前沿 | 新方法、新模型、新数据库 |
| 🧩 技能配方 | 可以照抄的 AI 用法、提示词、自动化工作流 |
| 📜 学术与合规 | 期刊政策、投稿要求、伦理规则 |
| 🚀 模型更新 | 大模型/平台的新能力、额度变化 |
| 📚 本期术语小抄 | 把本期出现的行话用大白话解释一遍 |

**条目数量不固定**：AI 打分达标的才放进来，最多 20 条，宁缺毋滥。
每一行都附原文链接，摘要只是帮你看得更快，重要内容请以原文为准。

---

## 第一次使用（照着做就行，大约 10 分钟）

### 第 1 步：创建一个空仓库

1. 打开 <https://github.com/new>
2. **Repository name** 填 `AI4Research-Weekly`
3. 选 **Public**（公共仓库的定时任务是免费的，额度也更宽松）
4. **不要**勾选 "Add a README file"，其它都不用动
5. 点 **Create repository**

### 第 2 步：准备一个 AI Key（两个方案二选一）

**方案 A：复用已有的 OpenAI Key（推荐，如果你本来就有）**
直接用你现有的 `OPENAI_API_KEY` 即可，什么都不用申请。

**方案 B：申请免费的 Gemini Key**
1. 打开 <https://aistudio.google.com/apikey>
2. 用 Google 账号登录 → 点 **Create API key**
3. 复制那串以 `AIza` 开头的字符

免费额度足够每周用：一次运行只调用 6～9 次接口。

> 两个都配也可以。程序会按 `code/config.py` 里 `LLM_PREFERENCE` 的顺序先试第一个，
> 整体跑不通（Key 失效、额度用完、模型名不对）会自动换第二个，不用你手动切换。

### 第 3 步：把 Secret 填进仓库

进你的仓库 → **Settings** → 左侧 **Secrets and variables** → **Actions**
→ 点绿色按钮 **New repository secret**：

| Name（名字） | Secret（值）填什么 |
| --- | --- |
| `OPENAI_API_KEY` | 你现有的 OpenAI Key（方案 A） |
| `GEMINI_API_KEY` | `AIza...` 那串（方案 B） |
| `QQMAIL` | 你的 QQ 邮箱**授权码**（不是登录密码，见下面怎么拿） |

> Base64 编码不需要，直接把内容粘进去就行。
> 邮件授权码这一项，`QQMAIL`、`Secret`、`QQ_AUTH_CODE` 这几个名字都能识别，
> 但名字随便起（比如 `mykey`）是认不出来的，建议统一用 `QQMAIL`。

**QQ 邮箱授权码怎么拿：**
1. 打开 <https://mail.qq.com> → 设置 → **账户**
2. 找到 **POP3/IMAP/SMTP 服务**，开启 **IMAP/SMTP 服务**（按提示用手机发一条短信验证）
3. 验证通过后会弹出一串 16 位字母，**那就是授权码**
4. 把它填进 `QQMAIL`。注意：这串码只显示一次，请顺手保存好

> 安全提醒：授权码等于邮箱的发送权限。只填进 GitHub Secret，不要写进代码文件，
> 也不要发在聊天里。如果怀疑泄露，回 QQ 邮箱重新生成一个即可。

### 第 4 步：立刻手动跑一次（不用等周三）

1. 仓库顶部点 **Actions**
2. 左侧点 **Weekly AI research brief**
3. 右侧点 **Run workflow** → 绿色按钮 **Run workflow**
4. 等 3～8 分钟，刷新页面，看到绿色 ✅ 就成功了
5. 去邮箱收信（第一次也可能进垃圾箱，标记为"非垃圾邮件"即可）

### 第 5 步：什么都不用做了

之后每周三早上 8:00 会自动运行并发送。

> 小提示：GitHub 的定时任务在高峰期可能晚 15～30 分钟，属于正常现象。
> 另外，公共仓库如果连续 60 天没有任何提交，定时任务会被自动停用——
> 本项目每次运行都会把去重历史提交回去，正好避免这个问题。

---

## 想改点东西？（都在 `code/config.py` 里）

这个文件是整份周报的控制面板，每一项上面都有中文注释，改完保存即可。常用的几项：

| 想做的事 | 改哪一项 |
| --- | --- |
| 觉得内容太少 | 把 `MIN_SCORE` 从 62 调低到 55 |
| 觉得内容太水 | 把 `MIN_SCORE` 调高到 70 |
| 想看更久之前的 | 把 `LOOKBACK_DAYS` 从 21 改成 30 |
| 每周最多几条 | 改 `MAX_ITEMS`（默认 20） |
| 不想收到空邮件 | 把 `SEND_EMPTY_NOTICE` 改成 `False` |
| 换 AI 平台或模型 | 改 `LLM_PREFERENCE`（谁优先）、`OPENAI_MODELS`、`GEMINI_MODELS` |
| 加一个新的信息源 | 在 `SOURCES` 末尾照格式复制一行 |
| 换栏目名字/颜色 | 改 `SECTIONS` |

### 怎么加一个 RSS 源？

在 `SOURCES` 列表末尾加一段（注意缩进和逗号）：

```python
    {
        "name": "某某博客",
        "kind": "rss",
        "url": "https://example.com/feed.xml",
        "pool": "工具雷达",
    },
```

`kind` 可选的类型：`rss`（博客/新闻）、`arxiv`（arXiv 论文）、`pubmed`（医学文献）、
`biorxiv` / `medrxiv`（预印本）、`github`（GitHub 仓库搜索）、`hf`（Hugging Face）、
`hn`（Hacker News）。

### 想换邮件长相？

邮件外观在 `templates/email.html`。里面写的是普通 HTML，
最上面的深色标题区搜 `#0f172a`、强调色搜 `#2563eb`，改颜色即可。

这个模板参考了 GitHub 上两个成熟的邮件排版项目：
[Cerberus](https://github.com/emailmonday/Cerberus)（5.1k★，响应式邮件排版范本）
和 [MJML](https://github.com/mjmlio/mjml)（18k★，邮件框架）。
邮件 HTML 和普通网页不同：必须用 `<table>` 排版、关键样式必须写成内联 `style`、
宽度固定 640px，否则在 QQ 邮箱和 Outlook 里会散架。模板已经按这些规矩处理好。

模板里可以用的占位符：

```
{{SUBJECT}} {{PREHEADER}} {{ISSUE_NO}} {{DATE_RANGE}} {{INTRO}}
{{RAW_COUNT}} {{ITEM_COUNT}} {{SOURCE_COUNT}} {{ROTATING_TOPIC}}
{{HIGHLIGHT_BLOCK}} {{SECTIONS_HTML}} {{GLOSSARY_BLOCK}}
{{FOOTER_NOTE}} {{SOURCES_NOTE}} {{FAILURE_NOTE}}
```

---

## 它是怎么工作的

```
① 抓取        arXiv / PubMed / bioRxiv / medRxiv / Hugging Face / GitHub /
              Hacker News / 官方博客 / 中文媒体 …… 共 20 个源
                          ↓
② 去重排序    按 URL 和标题去重 → 过滤无关内容 → 每个源限额 → 规则打分取前 90 条
                          ↓
③ 跳过旧闻    和 data/sent_history.json 比对，上周推过的不再推
                          ↓
④ AI 评审     分批交给 OpenAI 或 Gemini（谁先用谁由 LLM_PREFERENCE 决定）：
              归类到 5 个栏目 + 打 0-100 分 + 写"是什么/为什么/怎么做"
                          ↓
⑤ 渲染       套进 templates/email.html，生成 640px 宽的响应式邮件
                          ↓
⑥ 发送记录    QQ 邮箱 SMTP 发出 → 把这次发过的写入历史并提交回仓库
```

### 几个设计上的取舍（为什么这么做）

- **不装任何第三方库**：只用 Python 自带库，省掉 `pip install`，
  少一个环节就少一处可能失败的地方。
- **每个源都独立**：某个源被墙或改版，只会少几条内容，不会让整封邮件失败。
- **AI 挂了也有兜底**：先自动换另一家模型；两家都跑不通时，改用规则排序，
  仍然把最有价值的几条原文发给你，而不是发一封空信。
- **宁缺毋滥**：达不到分数就不放，所以有的周可能只有三四条。
- **去重历史必须提交**：否则每周都会重复推同样的东西。

---

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `code/config.py` | **你唯一需要经常改的文件**：所有参数和信息源清单 |
| `code/sources.py` | 抓取各信息源，统一成同一种格式 |
| `code/llm.py` | 调用 OpenAI / Gemini，含重试、模型自动切换、两家互为备份 |
| `code/curate.py` | 去重、预排序、AI 打分归类、选条目、写导读与术语小抄 |
| `code/render.py` | 把结果套进邮件模板，生成 HTML 和 Markdown |
| `code/history.py` | 跨周去重历史 |
| `code/send_email.py` | 通过 QQ 邮箱 SMTP 发信 |
| `code/run_weekly.py` | 主流程入口，GitHub Actions 执行的就是它 |
| `templates/email.html` | 邮件外观模板 |
| `data/sent_history.json` | 去重历史 + 期号（自动维护，别手动改） |
| `data/last_run.txt` | 每次运行的结果与日志末尾（自动生成，用来快速确认"跑了没、成没成"） |
| `data/run-now.txt` | "立刻发一封"开关：改动这个文件就会立刻运行一次 |
| `.github/workflows/weekly.yml` | 定时任务定义（每周三 00:00 UTC） |

---

## 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| Actions 里报 `没有找到 QQ 邮箱授权码` | Secret 名字不在可识别列表里，改成 `QQMAIL` 即可 |
| 报 `没有读到任何 AI 的 Key` | 请配置 `OPENAI_API_KEY` 或 `GEMINI_API_KEY` 之一 |
| 报 `OpenAI 拒绝了这个 Key（HTTP 401）` | Key 写错或已失效，重新复制一遍粘贴 |
| 报 `HTTP 429` 或额度相关错误 | 额度用完了，换另一个平台或等额度恢复 |
| 邮件没收到 | 先看 Actions 是否绿色；再去垃圾箱找；把发件人加入白名单 |
| 邮件里全是"本次 AI 摘要不可用" | AI Key 失效或额度用完，检查两家的 Key |
| 某周条目特别少 | 正常。本周确实没多少达标内容，或者大量内容上周已经推过 |
| 邮件在手机上排版乱 | 告诉我，或直接把 `templates/email.html` 的配色换掉试试 |
| 想立刻重跑一次 | 方法一：Actions → 左侧流程名 → Run workflow；方法二：在网页上编辑 `data/run-now.txt` 随便改一个字并提交 |
| 不知道到底跑成功没有 | 打开仓库里的 `data/last_run.txt`，第一行就是时间、触发方式和运行结果 |
| 想从头开始（清空已推记录） | 把 `data/sent_history.json` 里的 `items` 改回 `[]` |

---

## 成本

- GitHub Actions：公共仓库免费，本项目每次运行约 3～8 分钟。
- AI 接口：用你的 OpenAI Key，或 Gemini 的免费层级（一次运行 6～9 次调用）。
- 合计：**0 元**。
