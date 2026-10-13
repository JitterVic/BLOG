// 代码高亮：集中注册文章正文需要的语言，导出配置好的 hljs 实例。
//
// 注意：hljs.highlightElement() 在没有 language-* class 时会对整段内容做
// **自动语言猜测**。未知语言一旦被猜成 python/sql/bash/javascript，正文里的
// 目录树、YAML、Markdown 表格就会被涂上错误的 token 颜色（实测同一篇文章里
// 目录树被猜成 python、YAML 被猜成 sql、表格被猜成 bash）。
// 因此本项目禁用自动猜测：只高亮显式声明且已注册的语言，其余按纯文本处理，
// 由 highlightElement() 的调用方保证。

import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import css from "highlight.js/lib/languages/css";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import python from "highlight.js/lib/languages/python";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";

hljs.registerLanguage("bash", bash);
hljs.registerLanguage("css", css);
hljs.registerLanguage("javascript", javascript);
hljs.registerLanguage("json", json);
hljs.registerLanguage("python", python);
hljs.registerLanguage("sql", sql);
hljs.registerLanguage("typescript", typescript);
hljs.registerLanguage("xml", xml);

/** 取出 <code> 上声明的语言，没有则返回空串。 */
export function declaredLanguage(code) {
  const match = Array.from(code.classList).find((name) => name.startsWith("language-") || name.startsWith("lang-"));
  return match ? match.replace(/^languages?-|^lang-/, "").toLowerCase() : "";
}

/**
 * 只高亮「显式声明且已注册」的语言。
 * 返回真正用于高亮的语言名，未高亮时返回空串。
 */
export function highlightDeclared(code) {
  const language = declaredLanguage(code);
  if (!language || !hljs.getLanguage(language)) {
    code.classList.add("hljs");
    return "";
  }
  hljs.highlightElement(code);
  return language;
}

export { hljs };
export default hljs;
