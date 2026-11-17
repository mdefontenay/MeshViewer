document.querySelectorAll("[data-carousel]").forEach((carousel) => {
  const track = carousel.querySelector("[data-track]");
  const prev = carousel.querySelector("[data-prev]");
  const next = carousel.querySelector("[data-next]");
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const step = () => {
    const card = track.querySelector(".card");
    const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
    return card ? card.getBoundingClientRect().width + gap : track.clientWidth;
  };

  const update = () => {
    const max = track.scrollWidth - track.clientWidth - 2;
    prev.disabled = track.scrollLeft <= 2;
    next.disabled = track.scrollLeft >= max;
  };

  const go = (dir) => track.scrollBy({ left: dir * step(), behavior: reduceMotion ? "auto" : "smooth" });

  prev.addEventListener("click", () => go(-1));
  next.addEventListener("click", () => go(1));
  track.addEventListener("scroll", update, { passive: true });
  addEventListener("resize", update);
  update();
});

document.querySelectorAll("[data-code]").forEach((block) => {
  const button = block.querySelector("[data-copy]");
  const text = block.querySelector("code").innerText.trim();

  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.append(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    button.textContent = "Copied";
    button.classList.add("done");
    setTimeout(() => {
      button.textContent = "Copy";
      button.classList.remove("done");
    }, 1600);
  });
});
