(() => {
  const history = document.getElementById("briefing-history");
  if (matchMedia("(max-width: 720px)").matches) history.open = false;
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
