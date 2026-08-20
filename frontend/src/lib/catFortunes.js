// 科技签文、页面专属吐槽与极客箴言库 (Tech Fortune Cookies & Editorial Wisdom)

export const FORTUNES = [
  { text: "代码如诗，莫急于行。先想清楚再落笔。", tag: "思考" },
  { text: "所有的复杂，都源于最初没有厘清的一个简单概念。", tag: "架构" },
  { text: "遇事不决，先喝杯热茶，再跑一次单元测试。", tag: "日常" },
  { text: "重构是给未来的自己写情书。", tag: "重构" },
  { text: "过早的优化是万恶之源，但优雅的抽象从不嫌早。", tag: "箴言" },
  { text: "优秀的程序员不仅写机器能懂的代码，更写人能懂的逻辑。", tag: "工匠" },
  { text: "今天适合解决一个被搁置已久的小 bug！", tag: "运势" },
  { text: "保持好奇，长期主义是抵御技术迭代焦虑的最佳解药。", tag: "心态" },
  { text: "每一次键盘的敲击，都在塑造你的数字世界。", tag: "创造" },
  { text: "简单胜于复杂，平铺胜于嵌套，可读胜于晦涩。", tag: "哲学" },
  { text: "阅读技术文章就像翻阅纸质杂志，停顿才能内化理解。", tag: "伴读" },
  { text: "大吉！今日编译必过，网络请求零延迟 ✨", tag: "今日运势" },
  { text: "把复杂留给自己，把简单与优雅留给读者和用户。", tag: "设计" },
  { text: "任何优秀架构的第一要务，都是让删除代码变得容易。", tag: "整洁" },
  { text: "在喧嚣的信息洪流中，保持一份深度的纸墨专注。", tag: "专注" },
];

export const PAGE_DIALOGS = {
  home: [
    "欢迎光临至知的数字花园～ ☕",
    "今天想探索什么新知识呢？",
    "喝杯清茶，慢慢翻阅最新文章吧。",
  ],
  post: [
    "正在与你一同研读这篇文章 📖",
    "遇到精妙的段落，不妨多停顿思考一下哦。",
    "笔记已备好，随时记录灵感与心得 ✨",
  ],
  posts: [
    "这里汇聚了所有历史文章与技术笔记 🔍",
    "翻翻目录，找找你感兴趣的主题吧！",
    "按分类或标签筛选，探索更多灵感。",
  ],
  about: [
    "你好呀！我是博客的陪伴小猫 🐾",
    "关于作者、技术栈与设计理念都在这里～",
    "很高兴在此与你相遇！",
  ],
  "not-found": [
    "喵？迷路了吗？这个页面尚未收录呢 ❓",
    "别担心，点击下方带你安全返回目录～",
  ],
  default: [
    "静心阅读，享受代码与文字的质感 ✨",
    "点击我抽取一条今日极客签文吧～",
  ],
};

export const PET_STATUS_TEXTS = {
  idle: "悠闲伴读中",
  stretch: "舒服地伸个懒腰~",
  groom: "梳理一下毛发 ✨",
  eureka: "灵光一闪！💡",
  lookMouse: "好奇地盯住你的光标",
  pounce: "发现小光蝶！扑~",
  typing: "噼里啪啦狂敲代码中 ⌨️",
  dragging: "呜哇！被拎起来啦~ 🐾",
  petting: "呼噜呼噜~ 好舒服",
  sleeping: "呼呼大睡中... Zzz",
  launching: "火箭点火！飞向顶端 🚀",
};

export function getRandomFortune() {
  const index = Math.floor(Math.random() * FORTUNES.length);
  return FORTUNES[index];
}

export function getPageGreeting(routeName) {
  const list = PAGE_DIALOGS[routeName] || PAGE_DIALOGS.default;
  const index = Math.floor(Math.random() * list.length);
  return list[index];
}
