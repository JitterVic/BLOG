import { ref } from "vue";

import { getSite } from "../services/api";

const site = ref(null);
const loading = ref(false);
const error = ref("");

export function useSite() {
  async function ensureSite() {
    if (site.value || loading.value) {
      return;
    }

    loading.value = true;
    error.value = "";

    try {
      site.value = await getSite();
    } catch (err) {
      error.value = "站点信息加载失败，请稍后再试。";
      throw err;
    } finally {
      loading.value = false;
    }
  }

  return {
    site,
    loading,
    error,
    ensureSite,
  };
}


