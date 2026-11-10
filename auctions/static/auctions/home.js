(() => {
  const form = document.getElementById("home-search");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const url = new URL(form.action);
    for (const [key, value] of new FormData(form)) {
      const trimmed = value.trim();
      if (trimmed) url.searchParams.set(key, trimmed);
    }
    location.assign(url);
  });

  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  for (const rail of document.querySelectorAll("[data-home-rail]")) {
    const controls = rail.previousElementSibling.querySelector(".home-rail-controls");
    const buttons = controls.querySelectorAll("button");
    const update = () => {
      const canScroll = rail.scrollWidth - rail.clientWidth > 1;
      controls.hidden = !canScroll;
      for (const button of buttons) button.disabled = !canScroll;
    };

    function move(direction) {
      const limit = rail.scrollWidth - rail.clientWidth;
      const first = rail.firstElementChild;
      const second = first?.nextElementSibling;
      if (!second || limit <= 1) return;

      const step = second.getBoundingClientRect().left - first.getBoundingClientRect().left;
      const position = rail.scrollLeft;
      // Move the offscreen card before scrolling so the next full row stays filled.
      if (direction > 0 && position >= limit - 1) {
        rail.append(first);
        rail.scrollTo({ left: position - step, behavior: "instant" });
      } else if (direction < 0 && position <= 1) {
        rail.prepend(rail.lastElementChild);
        rail.scrollTo({ left: position + step, behavior: "instant" });
      }
      rail.scrollBy({ left: step * direction, behavior: motion.matches ? "instant" : "smooth" });
    }

    for (const button of buttons) {
      button.addEventListener("click", () => move(Number(button.dataset.step)));
    }
    rail.addEventListener("keydown", (event) => {
      if (event.target !== rail || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      move(event.key === "ArrowLeft" ? -1 : 1);
    });
    new ResizeObserver(update).observe(rail);
    update();
  }
})();
