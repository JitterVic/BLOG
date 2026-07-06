const API_ROOT = import.meta.env.VITE_API_ROOT || "/api";

async function request(path) {
  const response = await fetch(`${API_ROOT}${path}`);

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json();
}

export function getSite() {
  return request("/site");
}

export function getPosts(tagOrOptions = "", options = {}) {
  const params = typeof tagOrOptions === "object" ? tagOrOptions : { ...options, tag: tagOrOptions };
  const search = new URLSearchParams();

  if (params.tag) {
    search.set("tag", params.tag);
  }
  if (params.sort) {
    search.set("sort", params.sort);
  }
  if (params.limit) {
    search.set("limit", String(params.limit));
  }

  const suffix = search.toString() ? `?${search.toString()}` : "";
  return request(`/posts${suffix}`);
}

export function getPost(slug) {
  return request(`/posts/${slug}`);
}
