// SPDX-License-Identifier: AGPL-3.0-or-later
import * as helfer from "./helfer.js";

export const MAX_DATEI = 25 * 1024 * 1024;
export const MAX_ANHAENGE = 3;
export const MAX_NACHRICHT = 8000;
export const MAX_SEITEN = 200;
export const TEXT_ARTEN = [".txt", ".md", ".csv", ".html", ".htm"];
export const DATEI_ARTEN = [".pdf", ".docx", ...TEXT_ARTEN];
export const BILD_ARTEN = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".heif"];

export class AnhangFehler extends Error {}

const endung = (name) => (String(name).toLowerCase().match(/\.[a-z0-9]+$/) || [""])[0];
const sauber = (t) => String(t || "").replace(/\r\n?/g, "\n").replace(/[ \t ]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();


export function art(name, typ = "") {
  const e = endung(name);
  if (e === ".pdf") return "pdf";
  if (e === ".docx") return "docx";
  if (e === ".html" || e === ".htm") return "html";
  if (TEXT_ARTEN.includes(e)) return "text";
  if (BILD_ARTEN.includes(e) || /^image\//.test(typ)) return "bild";
  return null;
}


const MAX_ENTPACKT = 60 * 1024 * 1024;


async function inflate(roh, grenze = MAX_ENTPACKT) {
  const leser = new Blob([roh]).stream().pipeThrough(new DecompressionStream("deflate-raw")).getReader();
  const teile = [];
  let n = 0;
  try {
    for (;;) {
      const { done, value } = await leser.read();
      if (done) break;
      n += value.length;
      if (n > grenze) throw new AnhangFehler("Die Word-Datei ist zu groß.");
      teile.push(value);
    }
  } catch (e) {
    leser.cancel().catch(() => {});
    if (e instanceof AnhangFehler) throw e;
    throw new AnhangFehler("Die Word-Datei ist beschädigt.");
  }
  const aus = new Uint8Array(n);
  let p = 0;
  for (const t of teile) { aus.set(t, p); p += t.length; }
  return aus;
}


export async function zipDatei(bytes, gesucht) {
  const d = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let ende = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 65557); i--) if (d.getUint32(i, true) === 0x06054b50) { ende = i; break; }
  if (ende < 0) throw new AnhangFehler("Die Word-Datei ist beschädigt.");
  const anzahl = d.getUint16(ende + 10, true);
  let p = d.getUint32(ende + 16, true);
  const dec = new TextDecoder();
  for (let n = 0; n < anzahl && p + 46 <= bytes.length; n++) {
    if (d.getUint32(p, true) !== 0x02014b50) break;
    const methode = d.getUint16(p + 10, true), gross = d.getUint32(p + 20, true), klein = d.getUint32(p + 24, true);
    const nl = d.getUint16(p + 28, true), el = d.getUint16(p + 30, true), kl = d.getUint16(p + 32, true), lokal = d.getUint32(p + 42, true);
    const name = dec.decode(bytes.subarray(p + 46, p + 46 + nl));
    if (name === gesucht) {
      if (klein > MAX_ENTPACKT) throw new AnhangFehler("Die Word-Datei ist zu groß.");
      const start = lokal + 30 + d.getUint16(lokal + 26, true) + d.getUint16(lokal + 28, true);
      const roh = bytes.subarray(start, start + gross);
      if (methode === 0) return roh;
      if (methode === 8) return inflate(roh);
      throw new AnhangFehler("Diese Word-Datei ist ungewöhnlich gepackt.");
    }
    p += 46 + nl + el + kl;
  }
  return null;
}

export async function docxText(bytes) {
  const xml = await zipDatei(bytes, "word/document.xml");
  if (!xml) throw new AnhangFehler("Das ist keine Word-Datei (.docx).");
  const dok = new DOMParser().parseFromString(new TextDecoder().decode(xml), "application/xml");
  const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
  const absaetze = [];
  for (const absatz of dok.getElementsByTagNameNS(W, "p")) {
    let t = "";
    for (const k of absatz.getElementsByTagNameNS("*", "*")) {
      if (k.namespaceURI !== W) continue;
      if (k.localName === "t") t += k.textContent;
      else if (k.localName === "tab") t += "\t";
      else if (k.localName === "br") t += "\n";
    }
    absaetze.push(t);
  }
  return sauber(absaetze.join("\n"));
}


export function htmlText(quelle) {
  const dok = new DOMParser().parseFromString(String(quelle), "text/html");
  dok.querySelectorAll("script,style,noscript,template").forEach((e) => e.remove());

  dok.querySelectorAll("br,p,div,li,tr,h1,h2,h3,h4,h5,h6,section,article,header,footer,blockquote,pre,table,ul,ol,dt,dd")
    .forEach((e) => e.after("\n"));
  dok.querySelectorAll("td,th").forEach((e) => e.after("\t"));
  return sauber(dok.body?.textContent ?? "");
}


async function pdfText(bytes, fortschritt) {
  const pdfjs = await helfer.modul("pdfjs/pdf.min.mjs");
  pdfjs.GlobalWorkerOptions.workerSrc = await helfer.adresse("pdfjs/pdf.worker.min.mjs");
  const aufgabe = pdfjs.getDocument({ data: bytes, isEvalSupported: false, disableFontFace: true, enableXfa: false, useWorkerFetch: false });
  try {
    const dok = await aufgabe.promise;
    const seiten = Math.min(dok.numPages, MAX_SEITEN);
    const teile = [];
    let laenge = 0;
    for (let s = 1; s <= seiten && laenge < MAX_NACHRICHT * 4; s++) {
      fortschritt?.(`PDF wird gelesen: Seite ${s} von ${seiten}`);
      const inhalt = await (await dok.getPage(s)).getTextContent();
      const t = inhalt.items.map((i) => (i.str || "") + (i.hasEOL ? "\n" : " ")).join("");
      teile.push(t); laenge += t.length;
    }
    const text = sauber(teile.join("\n\n"));
    if (!text) throw new AnhangFehler("In dieser PDF steht kein lesbarer Text, vermutlich ist sie ein Scan. Fotografiere die Seite und häng sie als Foto an.");
    return { text, info: dok.numPages === 1 ? "1 Seite" : `${dok.numPages} Seiten` };
  } finally {
    await aufgabe.destroy();
  }
}


const SIMD = (() => {
  try { return WebAssembly.validate(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 253, 98, 11])); }
  catch { return false; }
})();

const SPRACHDATEN = "https://ki-helfer.invalid/lang";
const FOTO_ZEIT_S = 120;


function zeitgrenze(versprechen, s, text) {
  let uhr;
  return Promise.race([versprechen, new Promise((_, nein) => { uhr = setTimeout(() => nein(new AnhangFehler(text)), s * 1000); })])
    .finally(() => clearTimeout(uhr));
}

async function bildText(datei, fortschritt) {
  fortschritt?.("Die Texterkennung wird vorbereitet …");


  const [T, faden, kern, deu] = await Promise.all([
    helfer.modul("tesseract/tesseract.esm.min.js"),
    helfer.adresse("tesseract/worker.min.js"),
    helfer.adresse(SIMD ? "tesseract/core/tesseract-core-simd-lstm.wasm.js" : "tesseract/core/tesseract-core-lstm.wasm.js"),
    helfer.adresse("tesseract/lang/deu.traineddata.gz"),
  ]);


  const huelle = URL.createObjectURL(new Blob([
    `"use strict";(()=>{const echt=self.fetch.bind(self),daten=${JSON.stringify(deu)},weg=${JSON.stringify(SPRACHDATEN + "/deu.traineddata.gz")};` +
    `self.fetch=(u)=>String(u&&u.url||u)===weg?echt(daten):Promise.reject(new TypeError("gesperrt"));})();` +
    `importScripts(${JSON.stringify(faden)});`,
  ], { type: "text/javascript" }));
  const createWorker = T.createWorker || T.default?.createWorker;
  let w = null;
  try {
    w = await zeitgrenze(createWorker("deu", 1, {
      workerPath: huelle, corePath: kern + "#kern.js", langPath: SPRACHDATEN, workerBlobURL: false, cacheMethod: "none", gzip: true,
      logger: (m) => { if (m.status === "recognizing text") fortschritt?.(`Text im Foto wird gelesen: ${Math.round((m.progress || 0) * 100)} %`); },
      errorHandler: () => {},
    }), FOTO_ZEIT_S, "Die Texterkennung ließ sich nicht starten. Bitte noch einmal versuchen.");
    const { data } = await zeitgrenze(w.recognize(datei), FOTO_ZEIT_S, "Das Foto zu lesen hat zu lange gedauert.");
    const text = sauber(data?.text || "");
    if (text.length < 3) throw new AnhangFehler("Auf diesem Foto war kein Text zu lesen. KIplatz liest nur den Text aus Fotos, das Foto selbst bleibt auf deinem Handy.");
    return { text, info: "Text aus dem Foto" };
  } finally {
    URL.revokeObjectURL(huelle);
    try { await w?.terminate(); } catch { }
  }
}


export async function lesen(datei, fortschritt) {
  const a = art(datei.name, datei.type);
  if (!a) throw new AnhangFehler(`„${datei.name}“ kann KIplatz nicht lesen. Es gehen PDF, Word (.docx), Text und Fotos.`);
  if (datei.size > MAX_DATEI) throw new AnhangFehler(`„${datei.name}“ ist größer als 25 MB.`);
  if (a === "bild") return { name: datei.name, art: a, ...(await bildText(datei, fortschritt)) };
  const bytes = new Uint8Array(await datei.arrayBuffer());
  if (a === "pdf") return { name: datei.name, art: a, ...(await pdfText(bytes, fortschritt)) };
  if (a === "docx") return { name: datei.name, art: a, text: await docxText(bytes), info: "Word" };
  const roh = new TextDecoder().decode(bytes);
  const text = a === "html" ? htmlText(roh) : sauber(roh);
  if (!text) throw new AnhangFehler(`In „${datei.name}“ steht kein Text.`);
  return { name: datei.name, art: a, text, info: "Text" };
}


export function nachricht(frage, anhaenge) {
  frage = String(frage || "").trim();
  if (!anhaenge?.length) return { text: frage, mit: "", gekuerzt: [] };
  const koepfe = anhaenge.map((a) => `Datei „${a.name}“${a.info ? ` (${a.info})` : ""}:\n`);
  const rahmen = frage.length + 2 + koepfe.reduce((s, k) => s + k.length + 2, 0) + 40;
  let frei = Math.max(0, MAX_NACHRICHT - rahmen);
  const gekuerzt = [];
  const teile = [];

  const reihenfolge = anhaenge.map((a, i) => i).sort((x, y) => anhaenge[x].text.length - anhaenge[y].text.length);
  const anteil = new Array(anhaenge.length).fill(0);
  let offen = anhaenge.length;
  for (const i of reihenfolge) {
    const gerecht = Math.floor(frei / offen);
    anteil[i] = Math.min(anhaenge[i].text.length, gerecht);
    frei -= anteil[i]; offen--;
  }
  anhaenge.forEach((a, i) => {
    let t = a.text;
    if (t.length > anteil[i]) { t = t.slice(0, anteil[i]).replace(/\s+\S*$/, "") + " […]"; gekuerzt.push({ name: a.name, zeichen: anteil[i], von: a.text.length }); }
    teile.push(koepfe[i] + t);
  });
  const mit = teile.join("\n\n");
  return { text: frage, mit, gekuerzt };
}


export function inhalt(n) {
  return n.mit ? `${n.text}\n\n${n.mit}` : n.text;
}

export const MAX_BODY_BYTES = 56 * 1024;


export function verlaufBauen(nachrichten, maxBytes = MAX_BODY_BYTES) {
  const liste = nachrichten.filter((n) => (n.rolle === "user" || n.rolle === "assistant") && !n.fehler).slice(-20);
  let mitText = 0;
  const aus = [];
  for (let i = liste.length - 1; i >= 0; i--) {
    const n = liste[i];
    let content = n.text;
    if (n.mit) {
      mitText++;
      content = mitText <= 2 ? inhalt(n) : `${n.text}\n\n[angehängt war: ${(n.anhaenge || []).map((a) => "„" + a.name + "“").join(", ") || "eine Datei"}]`;
    }
    aus.unshift({ role: n.rolle, content });
  }
  const bytes = (x) => new TextEncoder().encode(JSON.stringify(x)).length;
  while (aus.length > 1 && bytes(aus) > maxBytes) aus.shift();
  return aus;
}
