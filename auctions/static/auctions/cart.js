(() => {
  const dialog = document.getElementById("site-cart");
  const opener = document.getElementById("cart-opener");
  const notice = document.getElementById("cart-notice");
  let pending = Promise.resolve();

  opener.addEventListener("click", (event) => {
    if (!dialog.showModal || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    dialog.showModal();
  });
  dialog.addEventListener("close", () => opener.focus({ preventScroll: true }));

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!form.matches("[data-cart-form]") || !event.submitter || !window.fetch) return;
    event.preventDefault();
    const button = event.submitter;
    const data = new FormData(form);
    data.set("action", button.value);
    button.disabled = true;
    pending = pending.then(async () => {
      try {
        const response = await fetch(form.getAttribute("action"), { method: "POST", body: data, headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error("cart");
        const result = await response.json();
        const active = document.activeElement;
        const content = Array.from(document.querySelectorAll("[data-cart-content]"));
        const focusInContents = content.some((panel) => panel.contains(active));
        for (const panel of content) panel.innerHTML = result.html;
        for (const count of document.querySelectorAll("[data-cart-count]")) count.textContent = result.count;
        const saved = new Set(result.ids);
        for (const candidate of document.querySelectorAll("[data-cart-form]:not([data-cart-remove])")) {
          const lot = candidate.elements.namedItem("lot");
          if (!lot) continue;
          const toggle = candidate.querySelector("button");
          const exists = saved.has(lot.value);
          toggle.value = exists ? "remove" : "add";
          toggle.setAttribute("aria-pressed", String(exists));
          toggle.textContent = exists ? "장바구니에서 빼기" : "장바구니에 담기";
        }
        if (focusInContents && dialog.open) dialog.querySelector("[data-close-cart]").focus();
        notice.textContent = "장바구니 " + result.count + "건";
      } catch {
        notice.textContent = "장바구니를 갱신하지 못했습니다. 다시 시도해 주세요.";
      } finally {
        button.disabled = false;
      }
    });
  });
})();
