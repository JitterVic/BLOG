// 编年索引分组：文章目录页与文章页左侧清单共用同一种年份分组，
// 避免同一段「按年切桶」的逻辑写两遍。

export function groupByYear(posts = []) {
  const groups = new Map();
  for (const post of posts) {
    const year = (post?.published_at || "未归档").slice(0, 4);
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year).push(post);
  }
  return Array.from(groups.entries());
}
