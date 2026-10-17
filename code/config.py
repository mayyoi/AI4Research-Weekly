# -*- coding: utf-8 -*-
"""
==========================================================
 这个文件是整份周报的"控制面板"。
 你 99% 的情况下只需要改这里，不用碰其它代码。
 每一项后面都有中文说明；看不懂的保持默认即可。
==========================================================
"""

# ---------------------------------------------------------
# 1. 邮件设置
# ---------------------------------------------------------
SENDER_EMAIL = "171142515@qq.com"      # 用哪个 QQ 邮箱发送（要和 GitHub Secret 里的授权码属于同一个邮箱）
RECEIVER_EMAIL = "171142515@qq.com"    # 发到哪个邮箱
EMAIL_SUBJECT = "AI × 科研效率周报"      # 邮件标题（后面会自动加上期号和日期）


# ---------------------------------------------------------
# 2. 内容筛选规则
# ---------------------------------------------------------
# 只看最近多少天内发布的内容。21 天 = 三周，避免漏掉上周没抓到的。
LOOKBACK_DAYS = 21

# 抓到的原始条目里，先挑多少条交给 AI 打分。
# 数字越大越慢、越费 AI 额度，但覆盖更全。90 是性价比比较高的值。
MAX_CANDIDATES = 90

# 每周邮件里最多放多少条。你要求"20 条以内的精华"，所以是 20。
MAX_ITEMS = 20

# AI 打分 0-100 分，低于这个分数就不推送。
# 调高 = 更挑（可能一周只有三五条）；调低 = 内容更多但可能变水。
MIN_SCORE = 62

# 如果筛完一条都不剩，是否仍然发一封"本周暂无值得推送"的短邮件。
# True = 你会知道流程还活着；False = 干脆不发，保持邮箱安静。
SEND_EMPTY_NOTICE = True

# 想屏蔽的词（标题里出现就丢弃）。用不上就留空列表。
BLOCKLIST = []


# ---------------------------------------------------------
# 3. AI 设置
# ---------------------------------------------------------
# 优先用哪家的模型。谁在前面就先试谁；某某整体跑不通会自动换下一个。
# 可用平台及所需凭据：
#   github   -> 仓库自带的 GITHUB_TOKEN（GitHub Models，免费，不需要你配任何 Key）
#   deepseek -> DEEPSEEK_API_KEY
#   openai   -> OPENAI_API_KEY（可选 OPENAI_BASE_URL 走中转）
#   gemini   -> GEMINI_API_KEY（免费额度）
LLM_PREFERENCE = ["github", "deepseek", "openai", "gemini"]

# GitHub Models 的模型名。会按顺序尝试，第一个不可用就换下一个。
# 不需要申请 Key，用的是工作流里自动注入的 GITHUB_TOKEN。
GITHUB_MODELS = [
    "openai/gpt-4.1-mini",
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "meta/Llama-4-Scout-17B-16E-Instruct",
]

# DeepSeek 的模型名
DEEPSEEK_MODELS = ["deepseek-chat"]

# OpenAI 用哪个模型。会按顺序尝试，第一个不存在就换下一个。
# 想指定固定模型，也可以在仓库里加一个叫 OPENAI_MODEL 的 Secret/Variable。
# OpenAI 的模型名（想固定用某个，也可以在仓库里加一个叫 OPENAI_MODEL 的变量）
OPENAI_MODELS = ["gpt-4.1-mini", "gpt-4o-mini", "gpt-4o", "gpt-4.1"]

# Gemini 用哪个模型（免费额度）。
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]

# 每次请求让 AI 处理多少条。太大容易超时或被截断，12 比较稳
# （推理型模型会先"思考"再输出，占用较多额度，所以不要调太大）。
AI_BATCH_SIZE = 12

# AI 请求最多重试几次（网络抖动/限流时有用）。
AI_MAX_RETRIES = 3

# 如果你想让 AI 更严格地只推"能帮到科研"的内容，可以改这段提示词的最后一句话。
EDITOR_PERSONA = (
    "你是一位既懂人工智能、又懂医学科研的资深编辑，"
    "服务对象是一名医学生/临床研究者。"
    "你的判断标准只有一条：这条消息能不能让他的科研工作更快、更省力、更靠谱。"
)


# ---------------------------------------------------------
# 4. 信息源清单
# ---------------------------------------------------------
# kind 的含义：
#   arxiv    = arXiv 论文接口
#   rss      = 博客/新闻网站的订阅源
#   github   = GitHub 仓库搜索（找新工具、新 skill）
#   biorxiv  = 生物/医学预印本
#   pubmed   = 医学文献库（找 AI 用于医学的新研究）
#   hf       = Hugging Face 每日精选论文
#   hn       = Hacker News 技术社区热帖
#
# pool = 这条源偏好的栏目（只是给 AI 的提示，最终栏目由 AI 判断）
# 想加源：照着格式复制一行即可。想关掉某条：在前面加 # 号。
# ---------------------------------------------------------
SOURCES = [
    # ---------- 方法前沿：论文与预印本 ----------
    {
        "name": "arXiv 人工智能",
        "kind": "arxiv",
        "query": "cat:cs.AI OR cat:cs.LG OR cat:cs.CL",
        "limit": 40,
        "pool": "方法前沿",
    },
    {
        "name": "arXiv 医学影像与生物信息",
        "kind": "arxiv",
        "query": "cat:eess.IV OR cat:q-bio.QM OR cat:q-bio.GN",
        "limit": 30,
        "pool": "方法前沿",
    },
    {
        "name": "Hugging Face 每日精选",
        "kind": "hf",
        "limit": 40,
        "pool": "方法前沿",
    },
    {
        "name": "bioRxiv 预印本",
        "kind": "biorxiv",
        "server": "biorxiv",
        "pool": "方法前沿",
    },
    {
        "name": "medRxiv 预印本",
        "kind": "biorxiv",
        "server": "medrxiv",
        "pool": "方法前沿",
    },
    {
        "name": "PubMed 医学 AI",
        "kind": "pubmed",
        "query": (
            '("artificial intelligence"[Title/Abstract] OR "large language model"[Title/Abstract] '
            'OR "deep learning"[Title/Abstract] OR "machine learning"[Title/Abstract]) '
            'AND (research OR diagnosis OR screening OR "systematic review" OR ophthalmology OR retina)'
        ),
        "limit": 40,
        "pool": "方法前沿",
    },

    # ---------- 工具雷达 / 技能配方：新工具、新 skill ----------
    {
        "name": "GitHub 新 AI 项目",
        "kind": "github",
        "query": "topic:llm created:>{since} stars:>25",
        "limit": 20,
        "pool": "工具雷达",
    },
    {
        "name": "GitHub 文献管理工具",
        "kind": "github",
        "query": "topic:zotero pushed:>{since} stars:>8",
        "limit": 15,
        "pool": "工具雷达",
    },
    {
        "name": "GitHub 笔记工具",
        "kind": "github",
        "query": "topic:obsidian-plugin pushed:>{since} stars:>15",
        "limit": 15,
        "pool": "工具雷达",
    },
    {
        "name": "GitHub MCP 生态",
        "kind": "github",
        "query": "topic:model-context-protocol pushed:>{since} stars:>20",
        "limit": 15,
        "pool": "技能配方",
    },
    {
        "name": "GitHub 生信新工具",
        "kind": "github",
        "query": "topic:bioinformatics created:>{since} stars:>10",
        "limit": 15,
        "pool": "方法前沿",
    },
    {
        "name": "Hacker News 热帖",
        "kind": "hn",
        "query": "AI",
        "limit": 30,
        "min_points": 50,
        "pool": "工具雷达",
    },

    # ---------- 官方更新与学术动态 ----------
    {
        "name": "OpenAI 官方动态",
        "kind": "rss",
        "url": "https://openai.com/news/rss.xml",
        "pool": "模型更新",
    },
    {
        "name": "Google AI 官方博客",
        "kind": "rss",
        "url": "https://blog.google/technology/ai/rss/",
        "pool": "模型更新",
    },
    {
        "name": "Google DeepMind 博客",
        "kind": "rss",
        "url": "https://deepmind.google/blog/rss.xml",
        "pool": "方法前沿",
    },
    {
        "name": "Nature Methods",
        "kind": "rss",
        "url": "https://www.nature.com/nmeth.rss",
        "pool": "方法前沿",
    },
    {
        "name": "Nature Biotechnology",
        "kind": "rss",
        "url": "https://www.nature.com/nbt.rss",
        "pool": "方法前沿",
    },
    {
        "name": "MIT 科技评论 · AI",
        "kind": "rss",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
        "pool": "学术与合规",
    },
    {
        "name": "量子位（中文）",
        "kind": "rss",
        "url": "https://www.qbitai.com/feed",
        "pool": "工具雷达",
    },
    {
        "name": "Simon Willison 博客",
        "kind": "rss",
        "url": "https://simonwillison.net/atom/everything/",
        "pool": "技能配方",
    },
]


# ---------------------------------------------------------
# 5. 邮件外观
# ---------------------------------------------------------
# 5 个栏目的顺序、图标、主题色。改颜色就改 theme。
SECTIONS = [
    {"key": "工具雷达", "icon": "🔧", "desc": "能直接上手的软件、网站、插件", "theme": "#2563eb"},
    {"key": "方法前沿", "icon": "🧪", "desc": "新方法、新模型、新数据库", "theme": "#7c3aed"},
    {"key": "技能配方", "icon": "🧩", "desc": "可照抄的 AI 用法与技巧", "theme": "#059669"},
    {"key": "学术与合规", "icon": "📜", "desc": "期刊政策、伦理、投稿规则", "theme": "#b45309"},
    {"key": "模型更新", "icon": "🚀", "desc": "大模型与平台的新能力", "theme": "#db2777"},
]

# 每期轮换的"专题"：会从这 5 个里按周轮换挑一个，让 AI 深挖。
ROTATING_TOPICS = [
    "文献检索与筛选",
    "文献阅读与笔记",
    "数据分析与统计",
    "论文写作与投稿",
    "科研自动化工作流",
]

# 邮件底部的小字
FOOTER_NOTE = (
    "本邮件由 GitHub Actions 自动生成并发送，每周三 08:00（北京时间）。"
    "所有条目均附原文链接，摘要为 AI 提炼，请以原文为准。"
)


# ---------------------------------------------------------
# 6. 追加：AI 技能（Skills）与社区一手实践
# ---------------------------------------------------------
# 这些源专门抓"别人怎么用 AI"。Reddit / V2EX / 少数派 都是公开订阅源，
# 不需要登录、不需要 cookie。抓不到会自动跳过，不影响整封邮件。
SOURCES.extend([
    {
        "name": "Reddit · ClaudeAI",
        "kind": "rss",
        "url": "https://www.reddit.com/r/ClaudeAI/new/.rss",
        "pool": "技能配方",
    },
    {
        "name": "Reddit · ChatGPTPro",
        "kind": "rss",
        "url": "https://www.reddit.com/r/ChatGPTPro/new/.rss",
        "pool": "技能配方",
    },
    {
        "name": "Reddit · LocalLLaMA",
        "kind": "rss",
        "url": "https://www.reddit.com/r/LocalLLaMA/new/.rss",
        "pool": "技能配方",
    },
    {
        "name": "V2EX 技术社区（中文）",
        "kind": "rss",
        "url": "https://www.v2ex.com/index.xml",
        "pool": "工具雷达",
    },
    {
        "name": "少数派（中文效率工具）",
        "kind": "rss",
        "url": "https://sspai.com/feed",
        "pool": "工具雷达",
    },
    {
        "name": "GitHub · Claude Skills",
        "kind": "github",
        "query": "topic:claude-skills pushed:>{since} stars:>5",
        "limit": 15,
        "pool": "技能配方",
    },
    {
        "name": "GitHub · Agent Skills",
        "kind": "github",
        "query": "topic:agent-skills pushed:>{since} stars:>5",
        "limit": 15,
        "pool": "技能配方",
    },
])
