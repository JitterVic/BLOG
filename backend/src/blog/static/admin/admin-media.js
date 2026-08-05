const mediaSearch = document.getElementById("media-search");
const mediaReferenceFilter = document.getElementById("media-reference-filter");
const mediaCards = Array.from(document.querySelectorAll("[data-media-card]"));
const mediaCount = document.getElementById("media-count");
const mediaEmpty = document.getElementById("media-filter-empty");

function filterMedia() {
  const query = (mediaSearch?.value || "").trim().toLowerCase();
  const referenceState = mediaReferenceFilter?.value || "";
  let visible = 0;

  mediaCards.forEach((card) => {
    const matchesQuery = !query || (card.dataset.search || "").includes(query);
    const matchesReference = !referenceState || card.dataset.referenceState === referenceState;
    const show = matchesQuery && matchesReference;
    card.hidden = !show;
    if (show) visible += 1;
  });

  if (mediaCount) mediaCount.textContent = `显示 ${visible} / ${mediaCards.length} 张图片`;
  if (mediaEmpty) mediaEmpty.hidden = visible !== 0;
}

async function copyText(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const input = document.createElement("textarea");
  input.value = value;
  input.style.position = "fixed";
  input.style.opacity = "0";
  document.body.appendChild(input);
  input.select();
  document.execCommand("copy");
  input.remove();
}

mediaSearch?.addEventListener("input", filterMedia);
mediaReferenceFilter?.addEventListener("change", filterMedia);

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-text]");
  if (!button) return;
  const original = button.textContent;
  try {
    await copyText(button.dataset.copyText || "");
    button.textContent = "已复制";
  } catch {
    button.textContent = "复制失败";
  }
  window.setTimeout(() => { button.textContent = original; }, 1200);
});
