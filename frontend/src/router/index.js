import { createRouter, createWebHistory } from "vue-router";

import AboutView from "../views/AboutView.vue";
import ArchiveView from "../views/ArchiveView.vue";
import HomeView from "../views/HomeView.vue";
import PostView from "../views/PostView.vue";
import PostsView from "../views/PostsView.vue";
import TagsView from "../views/TagsView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: HomeView,
    },
    {
      path: "/posts",
      name: "posts",
      component: PostsView,
    },
    {
      path: "/archive",
      name: "archive",
      component: ArchiveView,
    },
    {
      path: "/tags",
      name: "tags",
      component: TagsView,
    },
    {
      path: "/about",
      name: "about",
      component: AboutView,
    },
    {
      path: "/posts/:slug",
      name: "post",
      component: PostView,
    },
  ],
  scrollBehavior() {
    return {
      top: 0,
      behavior: "smooth",
    };
  },
});

export default router;
