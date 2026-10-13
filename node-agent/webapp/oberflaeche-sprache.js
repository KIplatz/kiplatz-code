// SPDX-License-Identifier: AGPL-3.0-or-later
(function (g) {
  "use strict";
  const SCHLUESSEL = "kiplatz.sprache";
  const ATTRIBUTE = ["placeholder", "title", "aria-label", "alt"];
  const genau = new Map();
  const muster = [];
  const fehlend = new Set();
  const original = new WeakMap();
  const attrOriginal = new WeakMap();
  let uebersetzte = [];
  let aktiv = "de";
  let beobachter = null;
  let ausnahme = "";
  const hoerer = [];

  function norm(s) { return String(s).replace(/\s+/g, " ").trim(); }
  function esc(s) { return s.replace(/[.*+?^$()|[\]\\]/g, "\\$&"); }

  function gewaehlt() {
    try { const w = localStorage.getItem(SCHLUESSEL); return w === "de" || w === "en" ? w : "auto"; } catch (e) { return "auto"; }
  }
  function geraet() {
    const l = (g.navigator && ((g.navigator.languages && g.navigator.languages[0]) || g.navigator.language)) || "de";
    return /^de\b/i.test(l) ? "de" : "en";
  }
  function sprache() { const w = gewaehlt(); return w === "auto" ? geraet() : w; }

  function katalogLaden(obj) {
    genau.clear(); muster.length = 0;
    for (const [de, en] of Object.entries(obj || {})) {
      if (typeof en !== "string" || !en.trim()) continue;
      const k = norm(de);
      if (/\{\d+\}/.test(k)) {

        if ((k.replace(/\{\d+\}/g, "").match(/[A-Za-zÄÖÜäöüß]/g) || []).length < 4) continue;
        const teile = k.split(/\{(\d+)\}/);
        let re = "^", reihe = [];
        teile.forEach((t, i) => { if (i % 2) { re += "(.+?)"; reihe.push(Number(t)); } else re += esc(t); });
        muster.push([new RegExp(re + "$"), en, reihe]);
      } else genau.set(k, en);
    }

    muster.sort((a, b) => b[0].source.replace(/\(\.\+\?\)/g, "").length - a[0].source.replace(/\(\.\+\?\)/g, "").length);
  }

  function deutschWirkend(s) { return /[A-Za-zÄÖÜäöüß]{2}/.test(s); }

  function zahlEn(w) { return /^[-+]?\d+,\d+(\s?[A-Za-z%]{1,3})?$/.test(w) ? w.replace(",", ".") : w; }


  function anfEn(w) { return w.replace(/„([^„“”]*)“/g, "“$1”"); }


  function saetze(k) {
    const aus = [], re = /[.!?…]["“”)]?\s+/g;
    let von = 0, m;
    while ((m = re.exec(k))) {
      const bis = m.index + m[0].length, vorn = k.slice(0, bis);
      if (/\d/.test(k[m.index - 1] || "") && !/[A-ZÄÖÜ„"“]/.test(k[bis] || "")) continue;
      if (/[a-zäöüß]/.test(k[bis] || "") || (vorn.match(/„/g) || []).length > (vorn.match(/“/g) || []).length) continue;
      aus.push(k.slice(von, bis).trim()); von = bis;
    }
    if (von < k.length) aus.push(k.slice(von).trim());
    return aus;
  }


  function luecke(w, tiefe) {
    const k = norm(w);
    let e;
    if (tiefe < 3) {
      const teile = k.includes(", ") ? k.split(", ") : [], neu = teile.map((x) => ganz(x, tiefe + 1, false));
      if (neu.length && neu.every((x) => x !== undefined)) return neu.join(", ");
      e = ganz(k, tiefe + 1, false);
      if (e === undefined && neu.some((x) => x !== undefined)) e = neu.map((x, i) => (x === undefined ? anfEn(zahlEn(teile[i])) : x)).join(", ");
    }
    return e !== undefined ? e : anfEn(zahlEn(w));
  }
  function finden(kern, tiefe) {
    const en = genau.get(kern);
    if (en !== undefined) return en;
    for (const [re, e, reihe] of muster) {
      const m = kern.match(re);
      if (m) { const w = {}; reihe.forEach((n, i) => { w[n] = luecke(m[i + 1], tiefe || 0); }); return e.replace(/\{(\d+)\}/g, (_, n) => (n in w ? w[n] : "")); }
    }
    return undefined;
  }


  function ganz(kern, tiefe, kurzOk, fehlt) {
    const lang = (x) => kurzOk || x.split(" ").length >= 3;
    if (!lang(kern)) return undefined;
    const en = genau.get(kern);
    if (en !== undefined) return en;
    const teile = saetze(kern);
    const neu = teile.length > 1 ? teile.map((x) => (lang(x) ? finden(x, tiefe) : undefined)) : [];
    if (neu.length && neu.every((x) => x !== undefined)) return neu.join(" ");
    const v = finden(kern, tiefe);
    if (v !== undefined) return v;
    if (!neu.some((x) => x !== undefined)) return undefined;
    return neu.map((x, i) => { if (x === undefined && fehlt) fehlt(teile[i]); return x === undefined ? teile[i] : x; }).join(" ");
  }

  function merken(kern) { if (deutschWirkend(kern) && kern.length <= 120 && fehlend.size < 300) fehlend.add(kern); }


  function t(text, werte) {
    if (typeof text !== "string") return text;
    let aus = text;
    if (aktiv === "en") {
      const kern = norm(text);
      if (!kern) return text;
      let en = ganz(kern, 0, true, merken);


      if (en === undefined && kern.includes(" · ")) {
        const vorn = kern.startsWith("· ") ? "· " : "", teile = kern.slice(vorn.length).split(" · ");
        const neu = teile.map((x) => { const e = finden(x); if (e === undefined) merken(x); return e === undefined ? x : e; });
        if (neu.some((x, i) => x !== teile[i])) en = vorn + neu.join(" · ");
      }
      if (en === undefined) merken(kern);
      else {
        const vorne = text.match(/^\s*/)[0], hinten = text.match(/\s*$/)[0];
        aus = vorne + en + hinten;
      }
    }
    if (werte) aus = aus.replace(/\{(\d+)\}/g, (m, n) => (n in werte ? String(werte[n]) : m));
    return aus;
  }

  function ausgenommen(el) {
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const tag = e.tagName;
      if (tag === "SCRIPT" || tag === "STYLE" || tag === "TEXTAREA" || tag === "CODE" || tag === "PRE") return true;
      if (e.getAttribute("translate") === "no" || e.isContentEditable) return true;
      if (ausnahme && e.matches(ausnahme)) return true;
    }
    return false;
  }

  function textKnoten(n) {
    const alt = original.get(n);
    if (alt && n.nodeValue === alt.en) return;
    const de = n.nodeValue;
    if (!de || !deutschWirkend(de) || ausgenommen(n.parentElement)) return;
    const en = t(de);
    if (en === de) return;
    original.set(n, { wert: de, en });
    uebersetzte.push(new WeakRef(n));
    n.nodeValue = en;
  }

  function attribute(el) {

    if (el.getAttribute("translate") === "no" || el.isContentEditable || (el.parentElement && ausgenommen(el.parentElement))) return;
    let alt = attrOriginal.get(el);
    const namen = ATTRIBUTE.slice();
    if (el.tagName === "INPUT" && /^(button|submit|reset)$/i.test(el.type)) namen.push("value");
    for (const a of namen) {
      const de = el.getAttribute(a);
      if (!de || !deutschWirkend(de)) continue;
      if (alt && alt[a] && alt[a].en === de) continue;
      const en = t(de);
      if (en === de) continue;
      if (!alt) { alt = {}; attrOriginal.set(el, alt); uebersetzte.push(new WeakRef(el)); }
      alt[a] = { wert: de, en };
      el.setAttribute(a, en);
    }
  }

  function baum(wurzel) {
    if (!wurzel) return;
    if (wurzel.nodeType === 3) { textKnoten(wurzel); return; }
    if (wurzel.nodeType !== 1 && wurzel.nodeType !== 9 && wurzel.nodeType !== 11) return;
    if (wurzel.nodeType === 1) { attribute(wurzel); if (ausgenommen(wurzel)) return; }
    const gang = document.createTreeWalker(wurzel, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        if (n.nodeType === 1) {
          const tag = n.tagName;
          if (tag === "TEXTAREA") { attribute(n); return NodeFilter.FILTER_REJECT; }
          if (tag === "SCRIPT" || tag === "STYLE" || n.getAttribute("translate") === "no" || (ausnahme && n.matches(ausnahme))) return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    let n;
    while ((n = gang.nextNode())) { if (n.nodeType === 3) textKnoten(n); else attribute(n); }
  }

  function beobachten() {
    if (beobachter || typeof MutationObserver === "undefined") return;
    beobachter = new MutationObserver((liste) => {
      if (aktiv !== "en") return;
      for (const m of liste) {
        if (m.type === "childList") m.addedNodes.forEach(baum);
        else if (m.type === "characterData") textKnoten(m.target);
        else if (m.type === "attributes") attribute(m.target);
      }
    });
    beobachter.observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRIBUTE.concat(["value"]) });
  }

  function titelSetzen() {
    if (!document.title) return;
    if (aktiv === "en") { const en = t(document.title); if (en !== document.title) { g.__kiplatzTitelDe = document.title; document.title = en; } }
    else if (g.__kiplatzTitelDe) { document.title = g.__kiplatzTitelDe; g.__kiplatzTitelDe = ""; }
  }

  function zurueckAufDeutsch() {
    for (const r of uebersetzte) {
      const n = r.deref();
      if (!n) continue;
      const o = original.get(n);
      if (o && n.nodeValue === o.en) n.nodeValue = o.wert;
      const a = attrOriginal.get(n);
      if (a) for (const [name, v] of Object.entries(a)) if (n.getAttribute(name) === v.en) n.setAttribute(name, v.wert);
    }
    uebersetzte = [];
  }

  function anwenden() {
    const neu = sprache();
    const vorher = aktiv;
    aktiv = neu;
    document.documentElement.lang = neu;
    if (neu === "en") { baum(document.body || document.documentElement); beobachten(); }
    else if (vorher === "en") zurueckAufDeutsch();
    titelSetzen();
    if (vorher !== neu) hoerer.forEach((f) => { try { f(neu); } catch (e) { } });
  }


  for (const name of ["alert", "confirm", "prompt"]) {
    const echt = g[name];
    if (typeof echt !== "function") continue;
    g[name] = function (text, ...rest) { return echt.call(g, t(text), ...rest); };
  }

  g.kiplatzSprache = {
    t,
    sprache,
    gewaehlt,
    aktiv: () => aktiv,

    datumSprache: () => (aktiv === "en" ? "en-GB" : "de-AT"),
    setzen(wahl) {
      try { if (wahl === "de" || wahl === "en") localStorage.setItem(SCHLUESSEL, wahl); else localStorage.removeItem(SCHLUESSEL); } catch (e) { }
      anwenden();
    },
    katalog(obj) { katalogLaden(obj); fehlend.clear(); if (aktiv === "en") baum(document.body); },
    beiWechsel(f) { hoerer.push(f); },

    ausnehmen(auswahl) { ausnahme = ausnahme ? ausnahme + ", " + auswahl : auswahl; },
    fehlend: () => [...fehlend].sort(),

    kopf: () => ({ "Accept-Language": aktiv === "en" ? "en" : "de" }),
    anwenden,
  };

  katalogLaden(g.KIPLATZ_TEXTE_EN);
  aktiv = sprache();
  if (typeof document !== "undefined") {
    document.documentElement.lang = aktiv;
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", anwenden, { once: true });
    else anwenden();
  }
})(globalThis);
