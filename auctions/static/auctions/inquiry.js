(() => {
  const fields = document.querySelector("[data-inquiry-fields]");
  if (!fields) return;
  const dialog = document.getElementById("auction-inquiry");
  const opener = document.querySelector("[data-open-inquiry]");
  const input = fields.querySelector("textarea");
  const status = fields.querySelector("[data-inquiry-status]");
  let opening = 0;

  if (dialog?.showModal) {
    opener.addEventListener("click", (event) => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (dialog.open) return;
      opening += 1;
      input.value = input.defaultValue;
      status.textContent = "";
      dialog.showModal();
    });
    dialog.addEventListener("close", () => opener.focus({ preventScroll: true }));
  }

  fields.querySelector("[data-copy-inquiry]").addEventListener("click", async () => {
    const message = input.value.trim();
    if (!message) {
      status.textContent = "복사할 문의 내용을 입력해 주세요.";
      input.focus();
      return;
    }

    const active = opening;
    const current = () => active === opening && (!dialog || dialog.open);
    try {
      await navigator.clipboard.writeText(message);
      if (current()) status.textContent = "문의 내용을 복사했습니다.";
    } catch {
      if (!current()) return;
      input.focus();
      input.select();
      status.textContent = "내용을 선택했습니다. 기기의 복사 기능을 사용해 주세요.";
    }
  });
})();
