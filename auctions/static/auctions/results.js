(() => {
  const stages = document.querySelector("[data-result-stages]");
  const links = [...stages.querySelectorAll("[data-status]")];
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  let content = document.getElementById("results-content");
  let pending;

  function setFilterVisibility(panel, open) {
    panel.open = Boolean(open || panel.querySelector(".errorlist"));
  }

  setFilterVisibility(content.querySelector("#result-filters"), !matchMedia("(max-width: 750px)").matches);

  async function showStatus(url, push) {
    pending?.abort();
    const controller = new AbortController();
    pending = controller;
    content.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(url, { signal: controller.signal });
      const html = new DOMParser().parseFromString(await response.text(), "text/html");
      if (controller.signal.aborted) return;
      const replacement = html.getElementById("results-content");
      const nextLinks = [...html.querySelectorAll("[data-result-stages] [data-status]")];
      if (!replacement || nextLinks.length !== links.length) throw new Error("Missing results content");
      setFilterVisibility(replacement.querySelector("#result-filters"), content.querySelector("#result-filters").open);
      for (const link of links) {
        const next = nextLinks.find((item) => item.dataset.status === link.dataset.status);
        link.setAttribute("href", next.getAttribute("href"));
        link.querySelector("[data-status-count]").textContent = next.querySelector("[data-status-count]").textContent;
        if (next.hasAttribute("aria-current")) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      }
      content.replaceWith(replacement);
      content = replacement;
      if (push && location.href !== url) history.pushState(null, "", url);
      if (!reducedMotion.matches) {
        content.querySelector(".results-list").animate(
          [{ opacity: .65, transform: "translateY(3px)" }, { opacity: 1, transform: "none" }],
          { duration: 220, easing: "ease-out" },
        );
      }
    } catch {
      if (!controller.signal.aborted) location.assign(url);
    } finally {
      if (pending === controller) {
        pending = undefined;
        content.removeAttribute("aria-busy");
      }
    }
  }

  stages.addEventListener("click", (event) => {
    const link = event.target.closest("[data-status]");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (link.href !== location.href || pending) showStatus(link.href, true);
  });
  window.addEventListener("popstate", () => showStatus(location.href, false));
})();
