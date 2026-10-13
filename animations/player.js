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
 *
 * Motion (skipped when the reader asks for reduced motion):
 *   - every element a step touches eases between states (opacity, color, position)
 *   - attribute changes (path d, x, width ...) and numbers count smoothly instead of jumping
 *   - going forward one step, the changes start one after another in drawing order (stagger),
 *     lines that appear draw themselves on, new text fades in, highlighted parts pulse once
 *   - the step title and explanation slide in
 * The end state of every step is exactly the same as without motion; `settle()` finishes it at once.
 */
(function () {
  "use strict";

  const reduceMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const MOTION = { stagger: 70, staggerMax: 560, tween: 700, draw: 900 };
  const easeInOut = (p) => (p < .5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2);
  const running = new Set();   // finish() of every tween in flight, for settle()

  /** Numbers in an attribute value, and the value with the numbers taken out (to check shapes match). */
  const NUM = /-?\d*\.?\d+(?:e[-+]?\d+)?/gi;
  function tweenAttr(node, name, to, delay) {
    const from = node.getAttribute(name);
    node.__tw = node.__tw || {};
    const token = {};
    node.__tw[name] = token;
    const a = from === null ? null : from.match(NUM), b = to.match(NUM);
    const same = a && b && a.length === b.length && from.replace(NUM, "#") === to.replace(NUM, "#");
    if (!same || from === to) { node.setAttribute(name, to); return; }
    const parts = to.split(NUM);
    const A = a.map(Number), B = b.map(Number);
    const write = (e) => node.setAttribute(name, parts.reduce((s, part, k) =>
      s + part + (k < B.length ? +(A[k] + (B[k] - A[k]) * e).toFixed(2) : ""), ""));
    const t0 = performance.now() + delay;
    const done = () => { running.delete(done); if (node.__tw[name] === token) { node.setAttribute(name, to); node.__tw[name] = null; } };
    running.add(done);
    const frame = (now) => {
      if (node.__tw[name] !== token) { running.delete(done); return; }   // finished early or replaced
      const p = Math.max(0, Math.min(1, (now - t0) / MOTION.tween));
      if (p >= 1) { done(); return; }
      write(easeInOut(p));
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }

  /** A line that has just appeared draws itself from start to end (skipped for dashed or arrowed lines). */
  function drawOn(node, delay) {
    const targets = node.tagName === "g" ? Array.from(node.querySelectorAll("path, line, polyline")).slice(0, 12) : [node];
    targets.forEach((n) => {
      if (!/^(path|line|polyline)$/.test(n.tagName) || n.hasAttribute("marker-end") || n.hasAttribute("marker-start")) return;
      const cs = getComputedStyle(n);
      if (cs.stroke === "none" || cs.strokeDasharray !== "none" || cs.animationName !== "none" || parseFloat(cs.strokeWidth) === 0) return;
      let len = 0;
      try { len = n.getTotalLength(); } catch (e) { return; }
      if (!(len > 12)) return;
      n.animate([{ strokeDasharray: len + " " + len, strokeDashoffset: len }, { strokeDasharray: len + " " + len, strokeDashoffset: 0 }],
        { duration: MOTION.draw, delay, easing: "cubic-bezier(.4, 0, .2, 1)" });
    });
  }

  /** Text that changed fades in (never makes a hidden element visible). */
  function fadeIn(node, delay) {
    if (parseFloat(getComputedStyle(node).opacity) === 0) return;
    node.animate([{ opacity: 0, offset: 0 }], { duration: 380, delay, easing: "ease-out" });
  }

  /** A part that just got highlighted pulses once. */
  const SHAPE = /^(rect|circle|ellipse|path|line|polyline|polygon)$/;
  function pulse(node, delay) {
    const targets = node.tagName === "g" ? Array.from(node.querySelectorAll("rect, circle, ellipse, path, line, polyline, polygon")).slice(0, 12) : [node];
    targets.forEach((n) => {
      if (SHAPE.test(n.tagName)) n.animate([{ strokeWidth: "5px", offset: .35 }], { duration: 900, delay, easing: "ease-in-out" });
    });
  }

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

  function tweenNumber(el, to, d, unit, delay) {
    const from = parseFloat(el.dataset.v);
    el.dataset.v = String(to);
    const show = (x) => { el.textContent = x.toFixed(d) + (unit || ""); };
    if (isNaN(from) || from === to || reduceMotion()) { show(to); return; }
    const t0 = performance.now() + (delay || 0);
    let over = false;
    const done = () => { over = true; running.delete(done); if (el.dataset.v === String(to)) show(to); };
    running.add(done);
    const step = (now) => {
      if (over) return;
      if (el.dataset.v !== String(to)) { running.delete(done); return; }
      const p = Math.max(0, Math.min(1, (now - t0) / MOTION.tween));
      if (p >= 1) { done(); return; }
      show(from + (to - from) * easeInOut(p));
      requestAnimationFrame(step);
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
    let ordered = [];       // [id, node] in drawing (document) order, for the stagger
    function collectIds() {
      allIds.clear();
      [opts.base].concat(modes.map((m) => m.base)).forEach((b) => idsIn(val(b, ctx), allIds));
      modes.forEach((m) => m.steps.forEach((s) => { idsIn(val(s.set, ctx), allIds); (s.hl || []).forEach((h) => allIds.add(h)); }));
      ordered = Array.from(allIds).map((id) => [id, el(id)]).filter((x) => x[1])
        .sort((x, y) => (x[1].compareDocumentPosition(y[1]) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
      // elements a page did not mark with .t still ease between states (see player.css .sp-tt)
      ordered.forEach((x) => { if (!x[1].classList.contains("t")) x[1].classList.add("sp-tt"); });
    }
    const original = new Map();
    const applied = new Map();   // id -> signature of the state last applied, to see what a step changes
    let started = false;         // no motion for the very first drawing
    function el(id) { return document.getElementById(id); }

    function stateAt(i) {
      const st = {};
      merge(st, val(opts.base, ctx));
      merge(st, val(mode.base, ctx));
      for (let k = 0; k <= i; k++) merge(st, val(mode.steps[k].set, ctx));
      return st;
    }

    function applyState(st, hl, rich) {
      const motion = started && !reduceMotion();
      let k = 0;
      ordered.forEach(([id, node]) => {
        if (!original.has(id)) original.set(id, { text: node.textContent, style: {}, attr: {} });
        const orig = original.get(id);
        const s = st[id] || {};
        const isHl = hl.indexOf(id) >= 0;
        const key = JSON.stringify([s.s, s.style, s.attr, s.text, s.num && s.num.v, isHl]);
        const changed = applied.has(id) && applied.get(id) !== key;
        applied.set(id, key);
        // going forward one step, the changes start one after another in drawing order
        const delay = motion && rich && changed ? Math.min(k++ * MOTION.stagger, MOTION.staggerMax) : 0;
        node.style.transitionDelay = delay ? delay + "ms" : "";
        const wasHidden = node.getAttribute("data-s") === "off";
        const wasHl = node.getAttribute("data-hl") === "1";
        if (s.s !== undefined) node.setAttribute("data-s", s.s); else node.removeAttribute("data-s");
        if (isHl) node.setAttribute("data-hl", "1"); else node.removeAttribute("data-hl");
        const style = s.style || {};
        Object.keys(orig.style).forEach((p) => { if (!(p in style)) node.style.removeProperty(p); });
        Object.keys(style).forEach((p) => { orig.style[p] = true; node.style.setProperty(p, style[p]); });
        const attr = s.attr || {};
        const setAttr = (a, v) => { if (motion) tweenAttr(node, a, String(v), delay); else { if (node.__tw) delete node.__tw[a]; node.setAttribute(a, v); } };
        Object.keys(attr).forEach((a) => {
          if (!(a in orig.attr)) orig.attr[a] = node.getAttribute(a);
          setAttr(a, attr[a]);
        });
        Object.keys(orig.attr).forEach((a) => {
          if (a in attr) return;
          if (orig.attr[a] === null) { if (node.__tw) delete node.__tw[a]; node.removeAttribute(a); } else setAttr(a, orig.attr[a]);
        });
        if (s.num) tweenNumber(node, s.num.v, s.num.d == null ? 2 : s.num.d, s.num.unit, delay);
        else if (s.text !== undefined) {
          if (node.textContent !== String(s.text)) { node.textContent = s.text; if (motion && rich && changed) fadeIn(node, delay); }
        } else if (!s.num && orig.text !== undefined && node.children.length === 0 && node.dataset.v === undefined) node.textContent = orig.text;
        if (motion && rich && changed) {
          if (wasHidden && s.s === "on") drawOn(node, delay);
          if (isHl && !wasHl) pulse(node, delay);
        }
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

    function go(i, how) {
      const n = mode.steps.length;
      const target = Math.max(0, Math.min(n - 1, i));
      const rich = started && how !== "jump" && target === index + 1;
      const moved = how === "jump" || target !== index;
      index = target;
      const step = mode.steps[index];
      applyState(stateAt(index), step.hl || [], rich);
      if (ui.count) ui.count.firstChild.nodeValue = (index + 1) + " / " + n + " ";
      if (ui.title) ui.title.textContent = val(step.title, ctx);
      if (ui.text) ui.text.innerHTML = val(step.text, ctx);
      if (started && moved && !reduceMotion()) [ui.title, ui.text].forEach((x) => {
        if (!x) return;
        x.classList.remove("sp-in"); void x.offsetWidth; x.classList.add("sp-in");
      });
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
      go(0, "jump");
      playLabel();
    }

    /** Finish every motion now (end state of the current step). */
    function settle() {
      Array.from(running).forEach((f) => f());
      document.getAnimations().forEach((an) => {
        const t = an.effect && an.effect.getComputedTiming();
        if (t && t.iterations !== Infinity) { try { an.finish(); } catch (e) { /* ignore */ } }
      });
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
            go(index, "jump");
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
    started = true;
    const api = { go, play, stop, setMode, settle, get index() { return index; }, get mode() { return mode.id; }, ctx };
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
