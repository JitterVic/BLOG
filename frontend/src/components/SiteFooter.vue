<script setup>
import { useSite } from "../composables/useSite";

const { site } = useSite();
const currentYear = new Date().getFullYear();
</script>

<template>
  <footer class="site-footer print-colophon">
    <div class="colophon-grid">
      <div class="colophon-brand">
        <div class="colophon__mark">{{ site?.name || "至知" }}.</div>
        <div class="colophon__issn">DIGITAL JOURNAL · {{ currentYear }}</div>
        <p class="colophon__headline">{{ site?.headline || "记录成长的点点滴滴" }}</p>
      </div>

      <div class="colophon-block colophon-quote">
        <h4>Motto</h4>
        <p class="colophon-quote__text">功不唐捐，玉汝于成。愿每一次记录都成为向上的台阶，时间会把这些点滴装订成属于你的答案。</p>
      </div>
    </div>

    <div class="colophon__legal">
      <span>© {{ currentYear }} {{ site?.name || "至知" }}</span>
      <span class="colophon__legal-sep" aria-hidden="true">·</span>
      <span>日拱一卒</span>
    </div>
  </footer>
</template>
