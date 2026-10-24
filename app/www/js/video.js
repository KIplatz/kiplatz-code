// SPDX-License-Identifier: AGPL-3.0-or-later
import { basisAdresse } from "./schnittstelle.js";

const NUMMER = "[A-Za-z0-9_-]{11}(?![A-Za-z0-9_-])";
const MUSTER = new RegExp(`https?://(?:(?:(?:www|m)\\.)?youtube\\.com/watch\\?(?:[^\\s)\\]>]*&)?v=|youtu\\.be/)(${NUMMER})`, "g");


export function videoNummern(text, max = 2) {
  const aus = [];
  for (const m of String(text || "").matchAll(MUSTER)) {
    if (!aus.includes(m[1])) aus.push(m[1]);
    if (aus.length >= max) break;
  }
  return aus;
}


export function videoKarte(nummer, titel = "") {
  const k = document.createElement("div");
  k.className = "video-karte";
  if (titel) {
    const t = document.createElement("div");
    t.className = "video-titel";
    t.translate = false;
    t.textContent = titel;
    k.append(t);
  }
  const flaeche = document.createElement("div");
  flaeche.className = "video-flaeche";
  const knopf = document.createElement("button");
  knopf.type = "button";
  knopf.className = "video-knopf";
  knopf.textContent = "Video ansehen";
  knopf.addEventListener("click", () => {
    const f = document.createElement("iframe");
    f.src = `https://www.youtube-nocookie.com/embed/${nummer}?rel=0`;
    f.title = "YouTube";
    f.setAttribute("sandbox", "allow-scripts allow-same-origin allow-presentation");
    f.setAttribute("referrerpolicy", "strict-origin-when-cross-origin");
    f.setAttribute("allow", "fullscreen; picture-in-picture");
    f.setAttribute("allowfullscreen", "");
    flaeche.replaceChildren(f);
  });

  const bild = document.createElement("img");
  bild.className = "video-vorschau";
  bild.alt = "";
  bild.setAttribute("referrerpolicy", "no-referrer");
  bild.addEventListener("error", () => bild.remove());
  bild.src = `${basisAdresse()}/vorschau?v=${nummer}`;
  flaeche.append(bild, knopf);
  const klein = document.createElement("div");
  klein.className = "video-klein leise klein";
  const hinweis = document.createElement("span");
  hinweis.textContent = "Beim Ansehen lädt YouTube das Video, dabei gehen Daten an YouTube.";
  const link = document.createElement("a");
  link.href = `https://www.youtube.com/watch?v=${nummer}`;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Auf YouTube öffnen";
  klein.append(hinweis, " ", link);
  k.append(flaeche, klein);
  return k;
}


export function videosAusLieferschein(videos, max = 2) {
  const aus = [];
  for (const v of Array.isArray(videos) ? videos : []) {
    const nummer = String(v?.nummer ?? "");
    if (/^[A-Za-z0-9_-]{11}$/.test(nummer) && !aus.some((x) => x.nummer === nummer)) aus.push({ nummer, titel: String(v?.titel ?? "").slice(0, 160) });
    if (aus.length >= max) break;
  }
  return aus;
}


export function videoKarten(text, videos = []) {
  const liste = videosAusLieferschein(videos);
  for (const nummer of videoNummern(text)) if (liste.length < 2 && !liste.some((x) => x.nummer === nummer)) liste.push({ nummer, titel: "" });
  return liste.map((v) => videoKarte(v.nummer, v.titel));
}
