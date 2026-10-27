import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("../views/HomeView.vue"),
    },
    {
      path: "/posts",
      name: "posts",
      component: () => import("../views/PostsView.vue"),
    },
    {
      path: "/notes",
      name: "notes",
      component: () => import("../views/NotesView.vue"),
    },
    {
      path: "/notes/:slug",
      name: "note",
      component: () => import("../views/NoteView.vue"),
    },
    {
      path: "/about",
      name: "about",
      component: () => import("../views/AboutView.vue"),
    },
    {
      path: "/posts/:slug",
      name: "post",
      component: () => import("../views/PostView.vue"),
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("../views/NotFoundView.vue"),
    },
  ],
  scrollBehavior(to, from, savedPosition) {
    // 换页回顶是瞬时的（动效只有 §7 四件）；文内锚点跳转保留平滑
    if (savedPosition) {
      return savedPosition;
    }

    if (to.hash) {
      const behavior = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth";
      return { el: to.hash, top: 72, behavior };
    }

    return { top: 0, behavior: "auto" };
  },
});

export default router;
