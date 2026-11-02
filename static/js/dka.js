/* ==========================================================================
   DKA DIGITAL — global UI behaviour
   - Lucide icons
   - Navbar scroll state + mobile drawer
   - Reveal-on-scroll
   - Flash message dismiss
   - Split-flap departure board animation
   ========================================================================== */
(function () {
  "use strict";
  document.documentElement.classList.remove("no-js");

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Icons ------------------------------------------------------------- */
  function renderIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });
    }
  }
  window.dkaRenderIcons = renderIcons;

  /* Navbar ------------------------------------------------------------ */
  function initNav() {
    const nav = document.querySelector("[data-nav]");
    if (!nav) return;
    const onScroll = () => nav.classList.toggle("is-scrolled", window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });

    const toggle = nav.querySelector("[data-nav-toggle]");
    const drawer = nav.querySelector("[data-nav-drawer]");
    if (toggle && drawer) {
      toggle.addEventListener("click", () => {
        const open = drawer.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", String(open));
      });
      document.addEventListener("click", (e) => {
        if (!nav.contains(e.target)) {
          drawer.classList.remove("is-open");
          toggle.setAttribute("aria-expanded", "false");
        }
      });
    }
  }

  /* Reveal ------------------------------------------------------------ */
  function initReveal() {
    const items = document.querySelectorAll(".reveal");
    if (!items.length) return;
    if (reduceMotion || !("IntersectionObserver" in window)) {
      items.forEach((el) => el.classList.add("is-in"));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    items.forEach((el) => io.observe(el));
  }

  /* Flash ------------------------------------------------------------- */
  function initFlash() {
    document.querySelectorAll("[data-flash-close]").forEach((btn) => {
      btn.addEventListener("click", () => btn.closest(".flash")?.remove());
    });
  }

  /* Split-flap -------------------------------------------------------- */
  const FLAP_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:-·";

  function buildFlap(el) {
    const text = (el.dataset.flap || el.textContent || "").toUpperCase();
    const len = Math.max(text.length, Number(el.dataset.flapLen || 0));
    const padded = text.padEnd(len, " ");
    el.textContent = "";
    el.setAttribute("aria-label", text.trim());
    const cells = [];
    for (let i = 0; i < len; i += 1) {
      const c = document.createElement("span");
      c.className = "flap__c";
      c.setAttribute("aria-hidden", "true");
      c.textContent = reduceMotion ? padded[i] : " ";
      el.appendChild(c);
      cells.push({ node: c, target: padded[i] });
    }
    return cells;
  }

  function spinCell(cell, delay) {
    if (reduceMotion) return;
    const target = cell.target;
    let steps = 6 + Math.floor(Math.random() * 10);
    window.setTimeout(function tick() {
      if (steps <= 0) {
        cell.node.textContent = target;
        cell.node.classList.remove("is-flipping");
        return;
      }
      cell.node.textContent = FLAP_CHARS[Math.floor(Math.random() * FLAP_CHARS.length)];
      cell.node.classList.remove("is-flipping");
      void cell.node.offsetWidth; // restart animation
      cell.node.classList.add("is-flipping");
      steps -= 1;
      window.setTimeout(tick, 55);
    }, delay);
  }

  function initBoards() {
    const boards = document.querySelectorAll("[data-board]");
    if (!boards.length) return;

    const run = (board) => {
      board.querySelectorAll("[data-flap]").forEach((el, i) => {
        const cells = buildFlap(el);
        cells.forEach((cell, j) => spinCell(cell, i * 40 + j * 25));
      });
    };

    boards.forEach((board) => {
      if (reduceMotion || !("IntersectionObserver" in window)) {
        run(board);
        return;
      }
      const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            run(entry.target);
            io.unobserve(entry.target);
          }
        });
      }, { threshold: 0.2 });
      io.observe(board);
    });

    // Live WAT clock
    document.querySelectorAll("[data-wat-clock]").forEach((clock) => {
      const fmt = new Intl.DateTimeFormat("en-GB", {
        hour: "2-digit", minute: "2-digit", second: "2-digit",
        hour12: false, timeZone: "Africa/Lagos",
      });
      const tick = () => { clock.textContent = fmt.format(new Date()) + " WAT"; };
      tick();
      window.setInterval(tick, 1000);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    renderIcons();
    initNav();
    initReveal();
    initFlash();
    initBoards();
  });
})();
