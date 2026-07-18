import { ref } from "vue";

import { getSite } from "../services/api";

const site = ref(null);
const loading = ref(false);
const error = ref("");
let siteRequest = null;

export function useSite() {
  async function ensureSite({ force = false } = {}) {
    if (site.value && !force) {
      return site.value;
    }

    if (siteRequest) {
      return siteRequest;
    }

    loading.value = true;
    error.value = "";

    siteRequest = getSite()
      .then((data) => {
        site.value = data;
        return data;
      })
      .catch((err) => {
        error.value = "站点信息加载失败，请稍后再试。";
        throw err;
      })
      .finally(() => {
        loading.value = false;
        siteRequest = null;
      });

    return siteRequest;
  }

  return {
    site,
    loading,
    error,
    ensureSite,
  };
}
