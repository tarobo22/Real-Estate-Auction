(() => {
  const trigger = document.querySelector(".briefing-history-trigger");
  const drawer = document.getElementById("briefing-history-drawer");
  if (trigger && drawer?.showModal) {
    trigger.hidden = false;
    trigger.addEventListener("click", () => drawer.showModal());
    drawer.addEventListener("click", (event) => {
      if (event.target === drawer) drawer.close();
    });
    drawer.addEventListener("close", () => trigger.focus({ preventScroll: true }));
    matchMedia("(max-width: 760px)").addEventListener("change", (event) => {
      if (!event.matches && drawer.open) drawer.close();
    });
  }

  const thread = document.querySelector("[data-briefing-thread]");
  if (thread?.querySelector(".briefing-turn")) thread.scrollTop = thread.scrollHeight;
  const form = document.getElementById("briefing-form");
  if (!form) return;
  const question = form.elements.namedItem("question");
  question.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    if (question.value.trim()) form.requestSubmit();
  });
  form.addEventListener("submit", (event) => {
    if (!question.value.trim()) {
      event.preventDefault();
      question.focus();
    }
  });
  for (const button of document.querySelectorAll("[data-prompt]")) {
    button.addEventListener("click", () => {
      question.value = button.dataset.prompt;
      form.requestSubmit();
    });
  }
})();
