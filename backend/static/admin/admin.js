"use strict";

const previewButton = document.getElementById("preview-button");
      const markdownInput = document.getElementById("markdown_content");
      const previewTarget = document.getElementById("preview-target");
      const previewMeta = document.getElementById("preview-meta");
      const markdownFileInput = document.getElementById("markdown-file");
      const uploadImageButton = document.getElementById("upload-image-button");
      const insertImageButton = document.getElementById("insert-image-button");
      const mediaFileInput = document.getElementById("media-file");
      const mediaResult = document.getElementById("media-result");
      const titleInput = document.getElementById("title");
      const slugInput = document.getElementById("slug");
      const excerptInput = document.getElementById("excerpt");
      const readTimeInput = document.getElementById("read_time");
      const categoryInput = document.querySelector('[name="category"]');
      const publishedAtInput = document.querySelector('[name="published_at"]');
      const tagsInput = document.querySelector('[name="tags"]');
      const heroQuoteInput = document.querySelector('[name="hero_quote"]');
      const coverImageInput = document.getElementById("cover_image");
      const frontPreviewCover = document.getElementById("front-preview-cover");
      const frontPreviewMeta = document.getElementById("front-preview-meta");
      const frontPreviewTitle = document.getElementById("front-preview-title");
      const frontPreviewExcerpt = document.getElementById("front-preview-excerpt");
      const frontPreviewQuote = document.getElementById("front-preview-quote");
      const frontPreviewTags = document.getElementById("front-preview-tags");
      const adminPostSearch = document.getElementById("admin-post-search");
      const adminPostStatus = document.getElementById("admin-post-status");
      const adminPostCount = document.getElementById("admin-post-count");
      const adminPostItems = Array.from(document.querySelectorAll("[data-post-item]"));
      let latestImageMarkdown = "";

      function escapeHtml(value = "") {
        return String(value).replace(/[&<>"']/g, (char) => ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        }[char]));
      }

      function splitTags(value = "") {
        return value
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
      }

      function setPreviewMessage(message, isError = false) {
        if (!previewMeta) return;
        previewMeta.textContent = message;
        previewMeta.style.color = isError ? "#991b1b" : "#64748b";
      }

      function updateFrontPreview() {
        if (!frontPreviewTitle) return;

        const title = titleInput?.value.trim() || "未命名文章";
        const category = categoryInput?.value.trim() || "Article";
        const publishedAt = publishedAtInput?.value.trim() || "未设置日期";
        const readTime = readTimeInput?.value.trim() || "1 min";
        const excerpt = excerptInput?.value.trim() || "这篇文章暂时还没有摘要。";
        const quote = heroQuoteInput?.value.trim() || "";
        const coverImage = coverImageInput?.value.trim() || "";
        const tags = splitTags(tagsInput?.value || "");

        frontPreviewTitle.textContent = title;
        frontPreviewExcerpt.textContent = excerpt;
        frontPreviewMeta.innerHTML = [category, readTime, publishedAt]
          .map((item) => `<span>${escapeHtml(item)}</span>`)
          .join("");

        frontPreviewQuote.textContent = quote;
        frontPreviewQuote.hidden = !quote;

        frontPreviewTags.hidden = tags.length === 0;
        frontPreviewTags.innerHTML = tags
          .map((tag) => `<span>#${escapeHtml(tag)}</span>`)
          .join("");

        if (coverImage) {
          frontPreviewCover.innerHTML = `<img src="${escapeHtml(coverImage)}" alt="${escapeHtml(title)}" />`;
        } else {
          frontPreviewCover.textContent = "无封面图时，前台显示文字卡片。";
        }
      }

      function updateAdminPostFilter() {
        if (!adminPostItems.length) return;
        const query = (adminPostSearch?.value || "").trim().toLowerCase();
        const status = adminPostStatus?.value || "";
        let visible = 0;

        adminPostItems.forEach((item) => {
          const matchesQuery = !query || (item.dataset.search || "").includes(query);
          const matchesStatus = !status || item.dataset.status === status;
          const shouldShow = matchesQuery && matchesStatus;
          item.classList.toggle("is-hidden", !shouldShow);
          if (shouldShow) visible += 1;
        });

        if (adminPostCount) {
          adminPostCount.textContent = (query || status)
            ? `显示 ${visible} / ${adminPostItems.length} 篇稿件`
            : `共 ${adminPostItems.length} 篇稿件`;
        }
      }

      function renderMediaResult({ url = "", message = "", isError = false } = {}) {
        mediaResult.classList.remove("is-error", "is-success");
        mediaResult.classList.add(isError ? "is-error" : "is-success");

        if (!url) {
          mediaResult.innerHTML = `<div class="result-copy">${escapeHtml(message || "操作未完成。")}</div>`;
          latestImageMarkdown = "";
          return;
        }

        const markdownSnippet = `![](${url})`;
        const safeUrl = escapeHtml(url);
        const safeMarkdown = escapeHtml(markdownSnippet);
        latestImageMarkdown = markdownSnippet;
        mediaResult.innerHTML = `
          <img src="${safeUrl}" alt="uploaded preview" class="result-preview" />
          <div class="result-copy">上传成功，可以直接复制下面两段中的任意一种使用。</div>
          <div class="copy-row"><code>${safeUrl}</code><button type="button" data-copy="${safeUrl}">复制 URL</button></div>
          <div class="copy-row"><code>${safeMarkdown}</code><button type="button" data-copy="${safeMarkdown}">复制 Markdown</button></div>
          <div class="copy-row"><code>${safeUrl}</code><button type="button" data-set-cover="${safeUrl}">设为封面</button></div>
        `;
      }

      async function fetchJson(url, options = {}) {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.message || `请求失败：${response.status}`);
        }
        return data;
      }

      previewButton?.addEventListener("click", async () => {
        try {
          setPreviewMessage("正在刷新预览……");
          const data = await fetchJson(document.body.dataset.previewUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ markdown_content: markdownInput.value }),
          });

          previewTarget.innerHTML = data.html || "<p>暂无预览内容</p>";
          setPreviewMessage(`预计阅读时间：${data.read_time} ｜ 自动摘要：${data.excerpt || "无"}`);
          if (!excerptInput.value && data.excerpt) excerptInput.value = data.excerpt;
          if (!readTimeInput.value && data.read_time) readTimeInput.value = data.read_time;
          updateFrontPreview();
        } catch (error) {
          setPreviewMessage(error.message || "预览失败，请稍后再试。", true);
        }
      });

      markdownFileInput?.addEventListener("change", async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("markdown_file", file);

        try {
          setPreviewMessage("正在导入 Markdown……");
          const data = await fetchJson(document.body.dataset.importUrl, {
            method: "POST",
            body: formData,
          });

          markdownInput.value = data.markdown_content || "";
          previewTarget.innerHTML = data.html_content || "";
          setPreviewMessage(`预计阅读时间：${data.read_time} ｜ 自动摘要：${data.excerpt || "无"}`);
          titleInput.value = data.title || titleInput.value;
          slugInput.value = data.slug || slugInput.value;
          excerptInput.value = data.excerpt || excerptInput.value;
          readTimeInput.value = data.read_time || readTimeInput.value;
          updateFrontPreview();
        } catch (error) {
          setPreviewMessage(error.message || "导入失败，请检查文件格式。", true);
        } finally {
          event.target.value = "";
        }
      });

      uploadImageButton?.addEventListener("click", async () => {
        const file = mediaFileInput.files?.[0];
        if (!file) {
          renderMediaResult({ message: "请先选择图片文件。", isError: true });
          return;
        }

        const formData = new FormData();
        formData.append("image", file);

        try {
          renderMediaResult({ message: "图片正在上传……" });
          const data = await fetchJson(document.body.dataset.uploadUrl, {
            method: "POST",
            body: formData,
          });
          renderMediaResult({ url: data.url });
        } catch (error) {
          renderMediaResult({ message: error.message || "上传失败，请稍后重试。", isError: true });
        }
      });

      mediaResult?.addEventListener("click", async (event) => {
        const coverButton = event.target.closest("[data-set-cover]");
        if (coverButton) {
          if (coverImageInput) {
            coverImageInput.value = coverButton.getAttribute("data-set-cover") || "";
            coverButton.textContent = "已设为封面";
            updateFrontPreview();
            setTimeout(() => (coverButton.textContent = "设为封面"), 1200);
          }
          return;
        }
        const button = event.target.closest("[data-copy]");
        if (!button) return;
        const text = button.getAttribute("data-copy") || "";
        try {
          await navigator.clipboard.writeText(text);
          button.textContent = "已复制";
          setTimeout(() => (button.textContent = text.startsWith("![") ? "复制 Markdown" : "复制 URL"), 1200);
        } catch (error) {
          renderMediaResult({ message: "复制失败，请手动选中内容复制。", isError: true });
        }
      });

      insertImageButton?.addEventListener("click", () => {
        if (!latestImageMarkdown) {
          renderMediaResult({ message: "请先上传图片，再插入到正文。", isError: true });
          return;
        }

        const spacer = markdownInput.value.trim() ? "\n\n" : "";
        markdownInput.value += `${spacer}${latestImageMarkdown}`;
        markdownInput.focus();
        renderMediaResult({ message: "图片 Markdown 已插入正文末尾。", url: latestImageMarkdown.match(/\((.*)\)/)?.[1] || "" });
      });

      [titleInput, categoryInput, publishedAtInput, readTimeInput, excerptInput, tagsInput, heroQuoteInput, coverImageInput]
        .forEach((input) => input?.addEventListener("input", updateFrontPreview));
      adminPostSearch?.addEventListener("input", updateAdminPostFilter);
      adminPostStatus?.addEventListener("change", updateAdminPostFilter);

      updateFrontPreview();
      updateAdminPostFilter();
