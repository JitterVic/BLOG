SITE_CONFIG = {
    "name": "至知",
    "role": "全栈开发者 / 开源爱好者 / 终身学习者",
    "headline": "记录成长的点点滴滴",
    "summary": (
        "这是一个参考 PaperGrid 气质重新实现的个人博客。"
        "我用 Flask 承载内容接口，用 Vue 搭建前台，让博客既像笔记本，也像作品集。"
    ),
    "location": "中国 · 热爱技术",
    "email": "hello@papernotes.dev",
    "hero_note": "在写代码，也在认真生活。",
    "social_links": [
        {
            "label": "邮箱",
            "value": "hello@papernotes.dev",
            "url": "mailto:hello@papernotes.dev",
            "icon": "mail",
        },
        {
            "label": "GitHub 仓库",
            "value": "github.com/yourname",
            "url": "https://github.com/yourname",
            "icon": "github",
        },
    ],
    "about_intro": [
        "这里主要记录我在开发、学习和写作过程中的阶段性思考。对我来说，博客不是单纯展示成果的地方，而是整理过程、复盘方法和沉淀长期能力的空间。",
        "我会把自己做过的练习、读过的资料、踩过的坑和解决方式慢慢写下来，让它既是公开文档，也是未来能反复回看的个人知识库。",
        "如果你也在做前端、后端或者个人项目，希望这些记录能给你一点参考，也欢迎通过邮箱或 GitHub 找到我交流。",
    ],
    "update_calendar": [
        {"date": "2026-03-21", "title": "首页改版为极简封面页"},
        {"date": "2026-03-18", "title": "补充文章详情页与相关文章模块"},
        {"date": "2026-03-15", "title": "新增归档页与标签页"},
        {"date": "2026-03-12", "title": "整理站点基础信息与内容结构"},
    ],
    "navigation": [
        {"label": "首页", "href": "/"},
        {"label": "文章", "href": "/posts"},
        {"label": "归档", "href": "/archive"},
        {"label": "标签", "href": "/tags"},
        {"label": "关于", "href": "/about"},
    ],
    "stats": [
        {"label": "已发布文章", "value": "03"},
        {"label": "正在进行的主题", "value": "05"},
        {"label": "年内目标", "value": "100 篇笔记"},
    ],
    "now_list": [
        "把博客当作公开成长记录，而不是只放“成品”的橱窗。",
        "练习把模糊想法写成能复用的工作流。",
        "尝试用更轻的技术栈做出更有气质的个人网站。",
    ],
    "timeline": [
        {"year": "2026", "text": "开始把个人博客升级为长期写作空间。"},
        {"year": "2025", "text": "持续记录开发实践与设计拆解。"},
        {"year": "2024", "text": "重新建立公开表达的习惯。"},
    ],
    "featured_slug": "building-a-paper-like-blog",
}

POSTS = [
    {
        "slug": "building-a-paper-like-blog",
        "title": "用 Flask + Vue 搭一个更像纸质笔记的个人博客",
        "excerpt": (
            "博客不一定只是时间线，它也可以像一本被认真编排过的笔记本，"
            "既能展示文章，也能表达你的气质。"
        ),
        "published_at": "2026-03-21",
        "read_time": "8 min",
        "category": "Build in Public",
        "featured": True,
        "tone": "amber",
        "tags": ["Flask", "Vue", "Blog", "Design"],
        "hero_quote": "把博客做成一个你愿意反复打开的地方。",
        "sections": [
            {
                "heading": "为什么从模板出发",
                "paragraphs": [
                    "从零开始做博客很容易陷入“功能全不全”的焦虑，但优秀模板最大的价值，是先帮你找到风格和信息结构。",
                    "PaperGrid 给我的启发不是复制页面，而是保留那种像纸张、像卡片、像被认真整理过的内容体验。",
                ],
            },
            {
                "heading": "为什么选 Flask + Vue",
                "paragraphs": [
                    "Flask 足够轻，适合做个人博客这类内容型项目，不会让后端复杂度盖过写作本身。",
                    "Vue 则很适合把首页、文章页和卡片组件组织成清晰的前台结构，后续扩展成标签筛选、搜索或后台管理都比较自然。",
                ],
            },
            {
                "heading": "这版先解决什么问题",
                "paragraphs": [
                    "第一版先把站点气质、文章结构和 API 边界确定下来，让博客能够被顺畅浏览。",
                    "有了这个基础，再接数据库、Markdown、部署流程或管理后台，会比一开始就全做更稳。",
                ],
            },
        ],
    },
    {
        "slug": "a-better-way-to-write-online",
        "title": "给个人博客一个“作品集”式的信息结构",
        "excerpt": (
            "写作型网站不一定要朴素到没有表情。通过首页模块化布局，"
            "读者可以先认识你，再走进你的文章。"
        ),
        "published_at": "2026-03-11",
        "read_time": "6 min",
        "category": "Writing System",
        "featured": False,
        "tone": "sage",
        "tags": ["Writing", "Information Architecture", "Portfolio"],
        "hero_quote": "首页先传递人格，再承接内容。",
        "sections": [
            {
                "heading": "内容不是越多越好",
                "paragraphs": [
                    "个人博客首页最常见的问题，是把所有文章平铺成列表，却没有先说明“这个人是谁、最近在关心什么”。",
                    "当首页有了自我介绍、当前状态和代表文章，读者会更容易理解这个站点的独特价值。",
                ],
            },
            {
                "heading": "让文章服务于个人品牌",
                "paragraphs": [
                    "如果你希望博客长期存在，它就不只是一个发布器，而是一个不断累积的个人资产。",
                    "因此页面结构应该帮助访客快速抓住你的主题、方法和审美，而不是让所有内容彼此竞争注意力。",
                ],
            },
        ],
    },
    {
        "slug": "designing-with-paper-grid",
        "title": "PaperGrid 风格里最值得借鉴的，不是排版，而是节奏",
        "excerpt": (
            "真正让人记住的并不是某一种边框或配色，而是页面里那种“停顿、留白、翻页感”带来的浏览节奏。"
        ),
        "published_at": "2026-02-25",
        "read_time": "5 min",
        "category": "Design Notes",
        "featured": False,
        "tone": "rose",
        "tags": ["UI", "Visual Design", "Inspiration"],
        "hero_quote": "节奏感，决定了一个博客像不像一本被设计过的刊物。",
        "sections": [
            {
                "heading": "不是复刻，而是翻译",
                "paragraphs": [
                    "把一个 Next.js 模板迁移到 Flask + Vue，本质上是一种视觉和交互语言的翻译。",
                    "我们保留纸感背景、结构化卡片和低饱和配色，但把技术实现换成更适合当前项目节奏的方案。",
                ],
            },
            {
                "heading": "留白是页面里的呼吸",
                "paragraphs": [
                    "真正高级的博客不是把模块堆满，而是让每个区块之间有足够的呼吸感。",
                    "这种节奏会让文章看起来更值得停留，也更容易建立属于你的风格识别度。",
                ],
            },
        ],
    },
]
