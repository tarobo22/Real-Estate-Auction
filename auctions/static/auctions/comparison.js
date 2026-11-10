(() => {
  const dialog = document.getElementById("vs-detail-dialog");
  const body = document.getElementById("vs-detail-body");
  const pair = document.querySelector(".vs-pair");
  const status = pair?.querySelector("[data-vs-status]");
  const buttons = document.querySelectorAll("[data-vs-slot]");
  let pending = false;
  let detailRequest = null;
  let opener = null;

  for (const form of document.querySelectorAll("[data-vs-choose]")) {
    form.addEventListener("submit", (event) => {
      if (!event.submitter) return;
      event.preventDefault();
      if (pending) return;
      pending = true;
      const button = event.submitter;
      const slot = button.matches(":focus-visible") ? button.dataset.vsSlot : "pointer";
      try { sessionStorage.setItem("auction-vs-focus", slot); } catch { /* Optional. */ }
      const winner = document.createElement("input");
      winner.type = "hidden";
      winner.name = "winner";
      winner.value = button.value;
      form.append(winner);
      button.closest(".vs-card").classList.add("is-selected");
      if (status) status.textContent = `매물 ${button.dataset.vsSlot} 선택 완료`;
      for (const candidate of buttons) candidate.disabled = true;
      const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
      setTimeout(() => form.submit(), reduced ? 0 : 350);
    });
  }

  if (document.querySelector(".versus-page")) {
    try {
      const slot = sessionStorage.getItem("auction-vs-focus");
      sessionStorage.removeItem("auction-vs-focus");
      if (slot) pair?.classList.add("is-entering");
      if (!new URLSearchParams(location.search).has("recommend")) {
        for (const button of buttons) if (button.dataset.vsSlot === slot) button.focus();
      }
    } catch { /* Optional. */ }
  }
  if (location.hash === "#winner-history") document.getElementById("winner-history")?.focus();

  const recommendation = document.getElementById("recommendation");
  const showRecommendation = document.querySelector("[data-open-recommendation]");
  if (recommendation?.showModal && showRecommendation) {
    showRecommendation.addEventListener("click", (event) => {
      event.preventDefault();
      recommendation.showModal();
    });
    recommendation.addEventListener("close", () => showRecommendation.focus({ preventScroll: true }));
    if (recommendation.dataset.auto === "1") {
      recommendation.showModal();
      const url = new URL(location.href);
      url.searchParams.delete("recommend");
      history.replaceState(null, "", url);
    }
  }

  if (!dialog?.showModal) return;
  for (const link of document.querySelectorAll("[data-vs-detail]")) {
    link.addEventListener("click", async (event) => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      opener = link;
      const controller = new AbortController();
      detailRequest = controller;
      body.textContent = "상세를 불러오는 중입니다.";
      dialog.showModal();
      const url = new URL(link.href);
      url.searchParams.set("fragment", "1");
      try {
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) throw new Error("detail");
        const content = await response.text();
        if (detailRequest === controller && dialog.open) body.innerHTML = content;
      } catch (error) {
        if (error.name !== "AbortError" && dialog.open) body.replaceChildren(link.cloneNode(true));
      }
    });
  }
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", () => {
    detailRequest?.abort();
    detailRequest = null;
    opener?.focus({ preventScroll: true });
  });
})();
