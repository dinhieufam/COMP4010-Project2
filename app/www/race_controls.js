(function () {
  "use strict";

  /* Per-chart state: { frameIdx, timer } */
  var _state = {};

  function getState(chartId) {
    if (!_state[chartId]) _state[chartId] = { frameIdx: 0, timer: null };
    return _state[chartId];
  }

  /* Apply frame idx — update chart, year badge, and slider.
     withAnim: smooth Plotly transition; false = instant (for seek / scrub) */
  function goTo(chartId, idx, withAnim) {
    var frames = (window._RACE_FRAMES || {})[chartId];
    var div    = document.getElementById(chartId);
    if (!div || !frames || idx < 0 || idx >= frames.length) return;

    var f = frames[idx];
    getState(chartId).frameIdx = idx;

    /* Keep HTML controls in sync */
    var yearEl   = document.getElementById(chartId + "-year");
    var sliderEl = document.getElementById(chartId + "-slider");
    if (yearEl)   yearEl.textContent = f.year;
    if (sliderEl) sliderEl.value     = idx;

    /* Build per-trace update arrays */
    var n = f.x.length;
    var traceData = [];
    for (var i = 0; i < n; i++) {
      traceData.push({ x: [f.x[i]], y: [f.y[i]], text: [f.text[i]] });
    }

    var dur = withAnim ? 600 : 0;
    Plotly.animate(
      div,
      { data: traceData, layout: { xaxis: { range: [0, f.maxX] } } },
      {
        transition: { duration: dur, easing: "cubic-in-out" },
        frame:      { duration: dur + 100, redraw: true },
        mode:       "immediate",
      }
    );
  }

  /* ── Public API ───────────────────────────────────────── */

  window.raceToggle = function (btn) {
    var chartId = btn.getAttribute("data-chart");
    var frames  = (window._RACE_FRAMES || {})[chartId];
    if (!frames) return;

    var s = getState(chartId);

    if (s.timer) {
      /* → Pause */
      clearInterval(s.timer);
      s.timer = null;
      btn.textContent = "▶︎  Play";
    } else {
      /* → Play */
      btn.textContent = "⏸︎  Pause";
      s.timer = setInterval(function () {
        var next = s.frameIdx + 1;
        if (next >= frames.length) {
          clearInterval(s.timer);
          s.timer = null;
          btn.textContent = "▶︎  Play";
          return;
        }
        goTo(chartId, next, true);
      }, 1500);
    }
  };

  /* Called by the HTML range input's oninput handler */
  window.raceSeek = function (chartId, idx) {
    /* Stop any running animation first */
    var s = getState(chartId);
    if (s.timer) {
      clearInterval(s.timer);
      s.timer = null;
      var btn = document.querySelector('[data-chart="' + chartId + '"]');
      if (btn) btn.textContent = "▶︎  Play";
    }
    goTo(chartId, idx, false);
  };
})();


/* ── Sticky tab-nav: pin exactly below filter bar ──────────────────────
   The CSS has a hardcoded top: 116px fallback, but the actual rendered
   height of (nav-pills + filter-bar) varies with zoom and font metrics.
   This JS measures both and overwrites the inline top so the tab nav
   sticks from the very first pixel of scroll, with zero travel. */
(function () {
  "use strict";

  var _roAttached = false;
  var _ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(run) : null;

  function run() {
    var pills  = document.querySelector(".mode-switcher-wrap .nav.nav-pills");
    var filter = document.querySelector(".explore-filter-bar");
    var tabNav = document.querySelector(".explore-content .nav-underline");
    if (!tabNav || !pills || !filter) return;
    tabNav.style.top = (pills.offsetHeight + filter.offsetHeight) + "px";
    /* Attach ResizeObserver once elements exist */
    if (_ro && !_roAttached) {
      _ro.observe(pills);
      _ro.observe(filter);
      _roAttached = true;
    }
  }

  window.addEventListener("resize", run);

  function burst() {
    [0, 80, 250, 600, 1400].forEach(function (d) { setTimeout(run, d); });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", burst);
  } else {
    burst();
  }
  document.addEventListener("shiny:connected", burst);
  document.addEventListener("shiny:idle",      run);

  /* Re-pin when user clicks any mode-switcher tab link */
  document.addEventListener("click", function (e) {
    var link = e.target && e.target.closest && e.target.closest(".mode-switcher-wrap .nav-link");
    if (link) setTimeout(burst, 30);
  });
})();
