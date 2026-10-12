/* Step player shared by the animations in this folder.
 *
 * A page describes its drawing as a list of steps. Each step names SVG elements by id and the
 * state they should be in from that step on:
 *   set: { "wl": { s: "on" }, "cell-fill": { style: { transform: "scaleY(.6)" } },
 *          "cell-v": { num: { v: 0.65, d: 2, unit: " V" } }, "bl-path": { attr: { d: "M..." } } }
 *   s     → data-s attribute (CSS decides what "on", "off", "void" ... look like)
 *   style → inline style properties (transform, opacity ...), animated by CSS transitions
 *   attr  → plain attributes (path d, x ...)
 *   text  → text content;  num → a number that counts to its new value
 * States add up: the drawing at step k is the base state plus steps 0..k, so jumping to any step
 * (or going back) always gives the same picture. `hl` lists ids highlighted only during that step.
 * Any value may be a function of the page context (e.g. the stored bit), so toggles redraw.
 */
(function () {
  "use strict";

  const reduceMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function val(x, ctx) { return typeof x === "function" ? x(ctx) : x; }

  function merge(into, set) {
    if (!set) return;
    Object.keys(set).forEach((id) => {
      const cur = into[id] || (into[id] = {});
      const next = set[id];
      Object.keys(next).forEach((k) => {
        if (k === "style" || k === "attr") cur[k] = Object.assign({}, cur[k], next[k]);
        else cur[k] = next[k];
      });
    });
  }

  function idsIn(set, out) {
    if (set && typeof set === "object") Object.keys(set).forEach((id) => out.add(id));
  }

  function tweenNumber(el, to, d, unit) {
    const from = parseFloat(el.dataset.v);
    el.dataset.v = String(to);
    const show = (x) => { el.textContent = x.toFixed(d) + (unit || ""); };
    if (isNaN(from) || from === to || reduceMotion()) { show(to); return; }
    const t0 = performance.now();
    const dur = 700;
    const step = (now) => {
      const p = Math.min(1, (now - t0) / dur);
      const e = p < .5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      show(from + (to - from) * e);
      if (p < 1 && el.dataset.v === String(to)) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function create(opts) {
    const root = opts.root;
    const q = (sel) => root.querySelector(sel);
    const ui = {
      count: q("[data-p=count]"), title: q("[data-p=title]"), text: q("[data-p=text]"), cmd: q("[data-p=cmd]"),
      list: q("[data-p=list]"), prev: q("[data-p=prev]"), next: q("[data-p=next]"), play: q("[data-p=play]"),
      first: q("[data-p=first]"), bar: q("[data-p=progress]"), modes: q("[data-p=modes]"), toggles: q("[data-p=toggles]"),
    };
    const ctx = Object.assign({}, opts.context);
    const modes = opts.modes || [{ id: "main", label: "", base: null, steps: opts.steps }];
    let mode = modes[0];
    const fromHash = location.hash.replace("#", "");
    if (fromHash) mode = modes.find((m) => m.id === fromHash) || mode;
    let index = 0;
    let timer = null;

    // Every id any step or base can touch, so a jump can reset what the target step does not set.
    const allIds = new Set();
    function collectIds() {
      allIds.clear();
      [opts.base].concat(modes.map((m) => m.base)).forEach((b) => idsIn(val(b, ctx), allIds));
      modes.forEach((m) => m.steps.forEach((s) => { idsIn(val(s.set, ctx), allIds); (s.hl || []).forEach((h) => allIds.add(h)); }));
    }
    const original = new Map();
    function el(id) { return document.getElementById(id); }

    function stateAt(i) {
      const st = {};
      merge(st, val(opts.base, ctx));
      merge(st, val(mode.base, ctx));
      for (let k = 0; k <= i; k++) merge(st, val(mode.steps[k].set, ctx));
      return st;
    }

    function applyState(st, hl) {
      allIds.forEach((id) => {
        const node = el(id);
        if (!node) return;
        if (!original.has(id)) original.set(id, { text: node.textContent, style: {}, attr: {} });
        const orig = original.get(id);
        const s = st[id] || {};
        if (s.s !== undefined) node.setAttribute("data-s", s.s); else node.removeAttribute("data-s");
        if (hl.indexOf(id) >= 0) node.setAttribute("data-hl", "1"); else node.removeAttribute("data-hl");
        const style = s.style || {};
        Object.keys(orig.style).forEach((p) => { if (!(p in style)) node.style.removeProperty(p); });
        Object.keys(style).forEach((p) => { orig.style[p] = true; node.style.setProperty(p, style[p]); });
        const attr = s.attr || {};
        Object.keys(attr).forEach((a) => {
          if (!(a in orig.attr)) orig.attr[a] = node.getAttribute(a);
          node.setAttribute(a, attr[a]);
        });
        Object.keys(orig.attr).forEach((a) => {
          if (!(a in attr)) { if (orig.attr[a] === null) node.removeAttribute(a); else node.setAttribute(a, orig.attr[a]); }
        });
        if (s.num) tweenNumber(node, s.num.v, s.num.d == null ? 2 : s.num.d, s.num.unit);
        else if (s.text !== undefined) node.textContent = s.text;
        else if (!s.num && orig.text !== undefined && node.children.length === 0 && node.dataset.v === undefined) node.textContent = orig.text;
      });
    }

    function renderList() {
      if (!ui.list) return;
      ui.list.innerHTML = "";
      mode.steps.forEach((s, i) => {
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.type = "button";
        b.innerHTML = '<span class="n">' + String(i + 1).padStart(2, "0") + "</span><span></span>";
        b.lastChild.textContent = val(s.short || s.title, ctx);
        b.addEventListener("click", () => { stop(); go(i); });
        li.appendChild(b);
        ui.list.appendChild(li);
      });
    }

    function go(i) {
      const n = mode.steps.length;
      index = Math.max(0, Math.min(n - 1, i));
      const step = mode.steps[index];
      applyState(stateAt(index), step.hl || []);
      if (ui.count) ui.count.firstChild.nodeValue = (index + 1) + " / " + n + " ";
      if (ui.title) ui.title.textContent = val(step.title, ctx);
      if (ui.text) ui.text.innerHTML = val(step.text, ctx);
      if (ui.cmd) ui.cmd.textContent = val(step.cmd, ctx) || "";
      if (ui.bar) ui.bar.style.width = ((index + 1) / n * 100) + "%";
      if (ui.prev) ui.prev.disabled = index === 0;
      if (ui.first) ui.first.disabled = index === 0;
      if (ui.next) ui.next.disabled = index === n - 1;
      if (ui.list) {
        Array.from(ui.list.querySelectorAll("button")).forEach((b, k) => {
          if (k === index) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
          b.classList.toggle("done", k < index);
        });
        const cur = ui.list.children[index];
        if (cur && cur.scrollIntoView && ui.list.scrollHeight > ui.list.clientHeight) {
          const top = cur.offsetTop - ui.list.offsetTop;
          if (top < ui.list.scrollTop || top > ui.list.scrollTop + ui.list.clientHeight - 40) ui.list.scrollTop = top - 40;
        }
      }
      playLabel();
      if (opts.onStep) opts.onStep({ index, mode: mode.id, ctx, step });
    }

    function playLabel() {
      if (!ui.play) return;
      const playing = timer !== null;
      ui.play.textContent = playing ? "멈춤" : (index === mode.steps.length - 1 ? "처음부터" : "재생");
      ui.play.setAttribute("aria-pressed", playing ? "true" : "false");
    }
    function stop() { if (timer) { clearTimeout(timer); timer = null; } playLabel(); }
    function tick() {
      const step = mode.steps[index];
      timer = setTimeout(() => {
        if (index >= mode.steps.length - 1) { stop(); return; }
        go(index + 1);
        tick();
      }, step.dur || opts.dur || 5200);
      playLabel();
    }
    function play() {
      if (timer) { stop(); return; }
      if (index >= mode.steps.length - 1) go(0);
      tick();
    }

    function setMode(id) {
      stop();
      mode = modes.find((m) => m.id === id) || modes[0];
      if (ui.modes) Array.from(ui.modes.querySelectorAll("button")).forEach((b) => b.setAttribute("aria-selected", b.dataset.mode === mode.id ? "true" : "false"));
      if (opts.onMode) opts.onMode(mode.id, ctx);
      renderList();
      go(0);
      playLabel();
    }

    // Mode tabs
    if (ui.modes && modes.length > 1) {
      modes.forEach((m) => {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = m.label;
        b.dataset.mode = m.id;
        b.setAttribute("role", "tab");
        b.addEventListener("click", () => { setMode(m.id); try { history.replaceState(null, "", "#" + m.id); } catch (e) { /* ignore */ } });
        ui.modes.appendChild(b);
      });
    }
    // Value toggles (context)
    if (ui.toggles && opts.toggles) {
      opts.toggles.forEach((t) => {
        const wrap = document.createElement("span");
        wrap.innerHTML = '<span class="seg-label"></span><span class="seg"></span>';
        wrap.firstChild.textContent = t.label;
        t.options.forEach(([v, label]) => {
          const b = document.createElement("button");
          b.type = "button";
          b.textContent = label;
          b.setAttribute("aria-pressed", ctx[t.id] === v ? "true" : "false");
          b.addEventListener("click", () => {
            ctx[t.id] = v;
            Array.from(wrap.querySelectorAll("button")).forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
            collectIds();
            renderList();
            go(index);
          });
          wrap.lastChild.appendChild(b);
        });
        ui.toggles.appendChild(wrap);
      });
    }

    if (ui.prev) ui.prev.addEventListener("click", () => { stop(); go(index - 1); });
    if (ui.next) ui.next.addEventListener("click", () => { stop(); go(index + 1); });
    if (ui.first) ui.first.addEventListener("click", () => { stop(); go(0); });
    if (ui.play) ui.play.addEventListener("click", play);
    document.addEventListener("keydown", (e) => {
      const tag = (e.target && e.target.tagName) || "";
      if (/INPUT|TEXTAREA|SELECT/.test(tag) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "ArrowRight") { stop(); go(index + 1); e.preventDefault(); }
      else if (e.key === "ArrowLeft") { stop(); go(index - 1); e.preventDefault(); }
      else if (e.key === "Home") { stop(); go(0); e.preventDefault(); }
      else if (e.key === "End") { stop(); go(mode.steps.length - 1); e.preventDefault(); }
      else if (e.key === " " && tag !== "BUTTON") { play(); e.preventDefault(); }
    });

    collectIds();
    setMode(mode.id);
    const api = { go, play, stop, setMode, get index() { return index; }, get mode() { return mode.id; }, ctx };
    window.__player = api;
    return api;
  }

  // Small drawing helpers shared by the pages.
  const NS = "http://www.w3.org/2000/svg";
  const kit = {
    NS,
    $: (id) => document.getElementById(id),
    /** Create an SVG element, set attributes, optional text, append to parent. */
    mk(parent, tag, attrs, text) {
      const n = document.createElementNS(NS, tag);
      Object.keys(attrs || {}).forEach((k) => n.setAttribute(k, attrs[k]));
      if (text != null) n.textContent = text;
      if (parent) parent.appendChild(n);
      return n;
    },
    /** The same state for many ids. */
    all(ids, v) { const o = {}; ids.forEach((i) => { o[i] = v; }); return o; },
    txt: (t) => ({ text: t }),
    on: { s: "on" },
    off: { s: "off" },
    /** Every id in `groups` hidden except those in `show`. */
    only(groups, show) { const o = {}; groups.forEach((g) => { o[g] = { s: show.indexOf(g) >= 0 ? "on" : "off" }; }); return o; },
    /** Text lines for ids prefix1..prefixN. */
    lines(prefix, arr, n) { const o = {}; for (let i = 1; i <= n; i++) o[prefix + i] = { text: (arr && arr[i - 1]) || "" }; return o; },
    /** Move an element to (x, y) with a CSS transform (animated by the player). */
    at(x, y, extra) { return { s: "on", style: { transform: `translate(${(+x).toFixed(1)}px, ${(+y).toFixed(1)}px)` + (extra ? " " + extra : "") } }; },
  };

  window.StepPlayer = { create, kit };
})();
