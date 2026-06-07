(function () {
  "use strict";

  // ── Scrolly steps: activate step + swap chart on scroll ──────────────────

  function makeStepObserver(chapter) {
    const steps  = document.querySelectorAll(`.scrolly-step[data-chapter="${chapter}"]`);
    const charts = document.querySelectorAll(`.scrolly-chart[data-chapter="${chapter}"]`);
    if (!steps.length) return;

    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          // fade step in/out (in-view class for dimmed state when not active)
          entry.target.classList.toggle("in-view", entry.isIntersecting);

          if (!entry.isIntersecting) return;
          const stepIndex = parseInt(entry.target.dataset.step, 10);

          // Toggle prose step active highlight
          steps.forEach((el) => el.classList.remove("is-active"));
          entry.target.classList.add("is-active");

          // Toggle chart visibility — each step has its own pre-rendered chart
          charts.forEach((el) => el.classList.remove("is-active"));
          const activeChart = document.querySelector(
            `.scrolly-chart[data-chapter="${chapter}"][data-step="${stepIndex}"]`
          );
          if (activeChart) activeChart.classList.add("is-active");
        });
      },
      { threshold: 0.55, rootMargin: "0px 0px -12% 0px" }
    );

    steps.forEach((el) => obs.observe(el));
  }

  // ── Section fade: chapters, act-breaks, finale fade in/out on scroll ─────

  function initSectionFade() {
    const targets = document.querySelectorAll(
      ".chapter, .scrolly-chapter, .act-break, .finale-section"
    );
    if (!targets.length) return;

    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          entry.target.classList.toggle("in-view", entry.isIntersecting);
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -5% 0px" }
    );
    targets.forEach((el) => obs.observe(el));
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  function init() {
    // Discover chapter IDs from the DOM
    const chapters = new Set(
      [...document.querySelectorAll(".scrolly-step[data-chapter]")].map(
        (el) => el.dataset.chapter
      )
    );
    chapters.forEach(makeStepObserver);
    initSectionFade();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    setTimeout(init, 400);
  }

  document.addEventListener("shiny:connected", () => setTimeout(init, 200));
})();
