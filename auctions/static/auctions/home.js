(() => {
  const form = document.getElementById("home-search");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const url = new URL(form.action);
    for (const [key, value] of new FormData(form)) {
      if (value.trim()) url.searchParams.set(key, value.trim());
    }
    location.assign(url);
  });

  const rails = Array.from(document.querySelectorAll(".rail"));
  function move(rail, direction) {
    const card = rail.querySelector(".home-lot");
    const end = rail.scrollWidth - rail.clientWidth;
    if (!card || end < 2) return;
    const step = card.offsetWidth + Number.parseFloat(getComputedStyle(rail).gap);
    const target = direction < 0 && rail.scrollLeft < 2 ? end
      : direction > 0 && rail.scrollLeft >= end - 2 ? 0 : rail.scrollLeft + direction * step;
    rail.scrollTo({ left: target, behavior: "smooth" });
  }

  for (const rail of rails) {
    const buttons = Array.from(document.querySelectorAll("[data-rail]"))
      .filter((button) => button.dataset.rail === rail.id);
    function update() {
      for (const button of buttons) button.hidden = rail.scrollWidth <= rail.clientWidth + 2;
    }
    for (const button of buttons) button.addEventListener("click", () => move(rail, Number(button.dataset.step)));
    rail.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      move(rail, event.key === "ArrowLeft" ? -1 : 1);
    });
    new ResizeObserver(update).observe(rail);
  }
})();
