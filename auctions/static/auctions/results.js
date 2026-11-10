(() => {
  const filters = document.getElementById("result-filters");
  if (matchMedia("(max-width: 750px)").matches && !filters.querySelector(".errorlist")) filters.open = false;
})();
