// SPDX-License-Identifier: AGPL-3.0-or-later
export function stuecke(text) {
  const aus = [];
  const re = /\*\*([^*\n]+)\*\*|`([^`\n]+)`/g;
  let rest = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > rest) aus.push({ art: "text", text: text.slice(rest, m.index) });
    aus.push(m[1] !== undefined ? { art: "fett", text: m[1] } : { art: "code", text: m[2] });
    rest = re.lastIndex;
  }
  if (rest < text.length) aus.push({ art: "text", text: text.slice(rest) });
  return aus;
}


const TRENNZEILE = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;
function zellen(zeile) {
  return zeile.trim().replace(/^\|/, "").replace(/(?<!\\)\|$/, "").split(/(?<!\\)\|/).map((z) => z.replace(/\\\|/g, "|").trim());
}
function istTabelle(zeilen, i) {
  return i + 1 < zeilen.length && zeilen[i].includes("|") && zeilen[i + 1].includes("|") && TRENNZEILE.test(zeilen[i + 1]);
}

function tabelleLesen(zeilen, i) {
  const kopf = zellen(zeilen[i]);
  const ausrichtung = zellen(zeilen[i + 1]).map((z) => (/^:-+:$/.test(z) ? "center" : /-:$/.test(z) ? "right" : ""));
  const reihen = [], roh = [];
  let j = i + 2;
  while (j < zeilen.length && zeilen[j].trim() && zeilen[j].includes("|")) { roh.push(zeilen[j]); reihen.push(zellen(zeilen[j++])); }
  const breite = Math.max(kopf.length, ...reihen.map((r) => r.length));
  const auf = (r) => r.concat(Array(breite - r.length).fill(""));
  return { block: { art: "tabelle", kopf: auf(kopf), ausrichtung: auf(ausrichtung), reihen: reihen.map(auf), roh }, weiter: j };
}


export function bloecke(text) {
  const zeilen = String(text || "").replace(/\r\n?/g, "\n").split("\n");
  const aus = [];
  let i = 0;
  while (i < zeilen.length) {
    const z = zeilen[i];
    if (/^```/.test(z)) {
      const code = [];
      i++;
      while (i < zeilen.length && !/^```/.test(zeilen[i])) code.push(zeilen[i++]);
      i++;
      aus.push({ art: "codeblock", text: code.join("\n") });
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(z);
    if (h) { aus.push({ art: "ueberschrift", text: h[2] }); i++; continue; }
    if (istTabelle(zeilen, i)) { const t = tabelleLesen(zeilen, i); aus.push(t.block); i = t.weiter; continue; }
    if (/^\s*[-*•]\s+/.test(z) || /^\s*\d+[.)]\s+/.test(z)) {
      const nummer = /^\s*\d+[.)]\s+/.test(z);
      const punkte = [];
      while (i < zeilen.length && (nummer ? /^\s*\d+[.)]\s+/ : /^\s*[-*•]\s+/).test(zeilen[i])) punkte.push(zeilen[i++].replace(/^\s*(?:[-*•]|\d+[.)])\s+/, ""));
      aus.push({ art: nummer ? "nummern" : "punkte", punkte });
      continue;
    }
    if (!z.trim()) { i++; continue; }
    const absatz = [];
    while (i < zeilen.length && zeilen[i].trim() && !/^```|^#{1,4}\s|^\s*[-*•]\s+|^\s*\d+[.)]\s+/.test(zeilen[i]) && !istTabelle(zeilen, i)) absatz.push(zeilen[i++]);
    aus.push({ art: "absatz", text: absatz.join("\n") });
  }
  return aus;
}


export function nurRueckfrage(lieferschein) {
  return lieferschein?.gemacht === "nachgefragt";
}


function tabelle(b) {
  const rahmen = document.createElement("div");
  rahmen.className = "tabelle-rahmen";
  rahmen.tabIndex = 0;
  rahmen.setAttribute("role", "region");
  rahmen.setAttribute("aria-label", "Tabelle");
  const t = document.createElement("table");
  const zelle = (tag, text, spalte) => {
    const z = document.createElement(tag);
    if (b.ausrichtung[spalte]) z.style.textAlign = b.ausrichtung[spalte];
    if (text.length <= 12) z.className = "kurz";
    inline(z, text);
    return z;
  };
  const kopf = document.createElement("tr");
  b.kopf.forEach((text, s) => kopf.append(zelle("th", text, s)));
  const thead = document.createElement("thead"); thead.append(kopf);
  const tbody = document.createElement("tbody");
  for (const reihe of b.reihen) {
    const tr = document.createElement("tr");
    tr.append(...reihe.map((text, s) => zelle("td", text, s)));
    tbody.append(tr);
  }
  t.append(thead, tbody);
  rahmen.append(t);
  return rahmen;
}

function inline(el, text) {
  for (const s of stuecke(text)) {
    if (s.art === "fett") { const b = document.createElement("strong"); b.textContent = s.text; el.append(b); continue; }
    if (s.art === "code") { const c = document.createElement("code"); c.textContent = s.text; el.append(c); continue; }
    if (s.text) el.append(s.text);
  }
}


export function zeichnen(el, text) {
  el.replaceChildren();
  for (const b of bloecke(text)) {
    let k;
    if (b.art === "codeblock") { k = document.createElement("pre"); const c = document.createElement("code"); c.textContent = b.text; k.append(c); }
    else if (b.art === "tabelle") k = tabelle(b);
    else if (b.art === "ueberschrift") { k = document.createElement("h3"); inline(k, b.text); }
    else if (b.art === "punkte" || b.art === "nummern") {
      k = document.createElement(b.art === "punkte" ? "ul" : "ol");
      for (const p of b.punkte) { const li = document.createElement("li"); inline(li, p); k.append(li); }
    } else { k = document.createElement("p"); inline(k, b.text); }
    el.append(k);
  }
}
