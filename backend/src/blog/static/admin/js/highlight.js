// 后台高亮：与前台 frontend/src/lib/highlight.js 同一策略。
//
// vendor 里的 highlight.min.js 是全语言版本，highlightElement() 在没有
// language-* class 时会自动猜测语言。正文里的目录树、YAML、Markdown 表格
// 经常被猜成 python/sql/bash，染上毫不相关的 token 颜色，所以这里禁用猜测：
// 只高亮显式声明且 hljs 认识的语言，其余仅补 .hljs 类以套用代码块配色。

export function highlightDeclared(code, hljs = window.hljs) {
  const match = Array.from(code.classList).find(
    (name) => name.startsWith("language-") || name.startsWith("lang-"),
  );
  const language = match ? match.replace(/^languages?-|^lang-/, "").toLowerCase() : "";
  if (!hljs || !language || !hljs.getLanguage(language)) {
    code.classList.add("hljs");
    return "";
  }
  hljs.highlightElement(code);
  return language;
}

