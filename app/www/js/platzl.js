// SPDX-License-Identifier: AGPL-3.0-or-later
import { ServerFehler, basisAdresse } from "./schnittstelle.js";
import * as tresor from "./tresor.js";
import { lesen as skillLesen } from "./skills.js";

export let FORUM = "https://forum.kiplatz.at";
let RUECK = "https://kiplatz.at";

export function entwicklungSetzen(ursprung) { FORUM = ursprung + "/schein-platzl"; RUECK = ursprung; }
const RECHTE = "read,write,session_info";
import { name as fachName } from "./konten.js";

const anfrage = () => "kiplatz." + fachName("platzl-anfrage");
const DB = "kiplatz-platzl", FACH = "schluessel";
const b64 = (u8) => btoa(String.fromCharCode(...u8));
const ausB64 = (s) => Uint8Array.from(atob(String(s).replace(/\s/g, "")), (c) => c.charCodeAt(0));
const zufall = (n) => [...crypto.getRandomValues(new Uint8Array(n))].map((x) => x.toString(16).padStart(2, "0")).join("");


function db() {
  return new Promise((ok, fehler) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(FACH);
    r.onsuccess = () => ok(r.result);
    r.onerror = () => fehler(r.error);
  });
}
async function fach(art, f) {
  const d = await db();
  try {
    return await new Promise((ok, fehler) => {
      const t = d.transaction(FACH, art);
      const r = f(t.objectStore(FACH));
      t.oncomplete = () => ok(r?.result);
      t.onerror = () => fehler(t.error);
    });
  } finally { d.close(); }
}

const paarLesen = () => fach("readonly", (s) => s.get(fachName("anfrage")));
const paarAblegen = (p) => fach("readwrite", (s) => s.put(p, fachName("anfrage")));
const paarLoeschen = () => fach("readwrite", (s) => s.delete(fachName("anfrage"))).catch(() => {});

export async function schluesselpaar() {
  return crypto.subtle.generateKey({ name: "RSA-OAEP", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-1" },
    false, ["encrypt", "decrypt"]);
}
export async function pem(oeffentlich) {
  const roh = b64(new Uint8Array(await crypto.subtle.exportKey("spki", oeffentlich)));
  return `-----BEGIN PUBLIC KEY-----\n${roh.match(/.{1,64}/g).join("\n")}\n-----END PUBLIC KEY-----\n`;
}

export async function antwortOeffnen(privat, payload, nonce) {
  let d;
  try {
    const klar = await crypto.subtle.decrypt({ name: "RSA-OAEP" }, privat, ausB64(payload));
    d = JSON.parse(new TextDecoder().decode(klar));
  } catch { throw new ServerFehler("Die Antwort des Platzl ließ sich nicht öffnen. Bitte noch einmal verbinden."); }
  if (!d || d.nonce !== nonce || typeof d.key !== "string" || !/^[A-Za-z0-9]{16,128}$/.test(d.key))
    throw new ServerFehler("Die Antwort des Platzl gehört nicht zu dieser Verbindung. Bitte noch einmal verbinden.");
  return d.key;
}


export const verbunden = async () => { try { const p = await tresor.lesen("platzl"); return p?.schluessel ? p : null; } catch { return null; } };
const offeneAnfrage = () => { try { const a = JSON.parse(localStorage.getItem(anfrage()) || "null"); return a && Date.now() - a.zeit < 600000 ? a : null; } catch { return null; } };
export const wartet = () => !!offeneAnfrage();


export async function verbindenStarten(holen, geraet) {
  const paar = await schluesselpaar();
  const ticket = zufall(16), nonce = zufall(16);
  const alt = await verbunden();
  const client = alt?.client || (await tresor.lesen("platzl-client").catch(() => null)) || zufall(16);
  await tresor.schreiben("platzl-client", client);
  await paarAblegen({ privat: paar.privateKey, ticket, nonce });
  await holen("/platzl-start", { body: { ticket }, geraet });
  localStorage.setItem(anfrage(), JSON.stringify({ ticket, nonce, zeit: Date.now() }));
  const q = new URLSearchParams({
    application_name: "KIplatz-App", client_id: client, scopes: RECHTE, public_key: await pem(paar.publicKey), nonce,
    auth_redirect: `${RUECK}/platzl-zurueck?t=${ticket}`, padding: "oaep",
  });
  return `${FORUM}/user-api-key/new?${q}`;
}


export async function abholen(holen, geraet) {
  const a = offeneAnfrage();
  if (!a) { localStorage.removeItem(anfrage()); return ""; }
  let r;
  try { r = await holen("/platzl-abholen", { body: { ticket: a.ticket }, geraet }); }
  catch (e) { if (e.status === 404) { localStorage.removeItem(anfrage()); await paarLoeschen(); } throw e; }
  if (r.status !== "fertig") return "wartet";
  const p = await paarLesen();
  localStorage.removeItem(anfrage());
  if (!p || p.ticket !== a.ticket) throw new ServerFehler("Diese Verbindung wurde auf einem anderen Weg begonnen. Bitte noch einmal verbinden.");
  const schluessel = await antwortOeffnen(p.privat, r.payload, a.nonce);
  await paarLoeschen();
  const client = await tresor.lesen("platzl-client");
  await tresor.schreiben("platzl", { schluessel, client, seit: new Date().toISOString() });
  try { const s = await api("/session/current.json"); const name = s?.current_user?.username; if (name) await tresor.schreiben("platzl", { schluessel, client, seit: new Date().toISOString(), name: String(name).slice(0, 60) }); } catch { }
  return "fertig";
}


const WEG = /^\/(session\/current|categories|latest|c\/[a-z0-9-]+\/\d+\/l\/latest|t\/\d+)\.json(\?page=\d{1,3})?$|^\/user-api-key\/revoke$|^\/posts\.json$/;


export async function api(weg, { body = null } = {}) {
  if (!WEG.test(weg)) throw new ServerFehler("ungültiger Weg");
  const p = await verbunden();
  if (!p) throw new ServerFehler("Das Platzl ist mit diesem Gerät nicht verbunden.", 0, "PLATZL_AUS");
  const abbruch = new AbortController();
  const uhr = setTimeout(() => abbruch.abort(), 20000);
  let r;
  try {
    r = await fetch(basisAdresse() + "/platzl-api" + weg, {
      method: body ? "POST" : "GET", credentials: "omit", cache: "no-store", redirect: "error", signal: abbruch.signal,
      headers: { "Accept": "application/json", "User-Api-Key": p.schluessel, "User-Api-Client-Id": p.client, ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ServerFehler(e.name === "AbortError" ? "Das Platzl hat nicht rechtzeitig geantwortet." : "Keine Verbindung zum Platzl. Bist du online?");
  } finally { clearTimeout(uhr); }
  if (r.status === 403 && weg !== "/user-api-key/revoke") {

    const s = weg === "/session/current.json" ? null : await api("/session/current.json").catch(() => null);
    if (!s?.current_user) { await tresor.loeschen("platzl"); throw new ServerFehler("Die Verbindung zum Platzl wurde beendet. Verbinde dich bitte neu.", 403, "PLATZL_AUS"); }
    throw new ServerFehler("Dafür fehlen dir im Platzl die Rechte.", 403);
  }
  if (r.status === 404) throw new ServerFehler("Das gibt es im Platzl nicht (mehr).", 404);
  if (r.status === 429) throw new ServerFehler("Das Platzl bremst gerade. Bitte in einer Minute noch einmal.", 429);
  if (r.status === 422) {
    let d = {};
    try { d = await r.json(); } catch { d = {}; }
    const grund = Array.isArray(d.errors) && typeof d.errors[0] === "string" ? d.errors[0].slice(0, 300) : "";
    throw new ServerFehler(grund ? `Das Platzl sagt: ${grund}` : "Das Platzl hat den Beitrag nicht angenommen.", 422);
  }
  if (!r.ok) throw new ServerFehler(`Das Platzl antwortet mit ${r.status}.`, r.status);
  try { return await r.json(); } catch { return {}; }
}

export const TITEL_MIN = 15, TEXT_MIN = 20, TEXT_MAX = 30000;


export async function schreiben({ titel = "", text, kategorie = null, thema = null }) {
  const raw = String(text || "").trim();
  if (raw.length < TEXT_MIN) throw new ServerFehler(`Der Text braucht mindestens ${TEXT_MIN} Zeichen.`);
  if (raw.length > TEXT_MAX) throw new ServerFehler(`Der Text ist zu lang (höchstens ${TEXT_MAX} Zeichen).`);
  let body;
  if (thema) body = { topic_id: Number(thema), raw };
  else {
    const t = String(titel || "").replace(/\s+/g, " ").trim();
    if (t.length < TITEL_MIN) throw new ServerFehler(`Der Titel braucht mindestens ${TITEL_MIN} Zeichen.`);
    if (!Number.isInteger(kategorie)) throw new ServerFehler("Bitte eine Kategorie wählen.");
    body = { title: t.slice(0, 250), raw, category: kategorie };
  }
  const d = await api("/posts.json", { body });
  return { thema: Number(d?.topic_id) || Number(thema) || 0, nummer: Number(d?.post_number) || 0 };
}


export async function trennen() {
  try { await api("/user-api-key/revoke", { body: {} }); } catch { }
  await tresor.loeschen("platzl");
}


const ERLAUBT = { P: "p", BR: "br", STRONG: "strong", B: "strong", EM: "em", I: "em", UL: "ul", OL: "ol", LI: "li", BLOCKQUOTE: "blockquote",
  CODE: "code", PRE: "pre", H1: "h4", H2: "h4", H3: "h4", H4: "h4", H5: "h4", H6: "h4", A: "a", DEL: "del", S: "del", HR: "hr" };
const UEBERSPRINGEN = new Set(["SCRIPT", "STYLE", "IFRAME", "OBJECT", "EMBED", "FORM", "INPUT", "BUTTON", "TEMPLATE", "SVG", "MATH", "NOSCRIPT", "VIDEO", "AUDIO", "SELECT", "TEXTAREA"]);

export function inhaltBauen(cooked) {
  const doc = new DOMParser().parseFromString(`<body>${String(cooked || "")}</body>`, "text/html");
  const ziel = document.createDocumentFragment();
  const gehen = (von, nach, tiefe) => {
    if (tiefe > 20) return;
    for (const n of von.childNodes) {
      if (n.nodeType === 3) { nach.append(document.createTextNode(n.nodeValue)); continue; }
      if (n.nodeType !== 1 || UEBERSPRINGEN.has(n.tagName)) continue;
      if (n.tagName === "IMG") {
        const alt = (n.getAttribute("alt") || "").trim();
        if (n.classList.contains("emoji")) nach.append(document.createTextNode(alt));
        else if (alt || n.getAttribute("src")) nach.append(document.createTextNode(`[Bild${alt ? ": " + alt : ""}]`));
        continue;
      }
      if (n.tagName === "ASIDE" && n.classList.contains("quote")) {
        const bq = document.createElement("blockquote");
        const wer = n.getAttribute("data-username");
        if (wer) { const s = document.createElement("strong"); s.textContent = `@${wer.slice(0, 60)}:`; bq.append(s, document.createElement("br")); }
        gehen(n.querySelector("blockquote") || n, bq, tiefe + 1);
        nach.append(bq); continue;
      }
      const tag = ERLAUBT[n.tagName];
      if (!tag) { gehen(n, nach, tiefe + 1); continue; }
      const el = document.createElement(tag);
      if (tag === "a") {
        let ziel = null;
        try { const u = new URL(n.getAttribute("href") || "", FORUM); if (u.protocol === "https:") ziel = u.href; } catch { ziel = null; }
        if (!ziel) { gehen(n, nach, tiefe + 1); continue; }
        el.href = ziel; el.target = "_blank"; el.rel = "noopener noreferrer";
      }
      gehen(n, el, tiefe + 1);
      nach.append(el);
    }
  };
  gehen(doc.body, ziel, 0);
  return ziel;
}


export function skillImBeitrag(cooked) {
  const doc = new DOMParser().parseFromString(`<body>${String(cooked || "")}</body>`, "text/html");
  const block = doc.querySelector("pre code") || doc.querySelector("pre");
  const text = block?.textContent || "";
  return text.trim().length >= 20 ? text : null;
}


export async function skillHolen(thema) {
  const d = await api(`/t/${Number(thema)}.json`);
  const roh = skillImBeitrag(d?.post_stream?.posts?.[0]?.cooked);
  if (!roh) throw new ServerFehler("In diesem Thema steht kein Skill (kein Codeblock im ersten Beitrag).");
  let s;
  try { s = skillLesen(roh); } catch (e) { throw new ServerFehler(e.message); }
  return { ...s, titel: String(d?.title || s.name).replace(/^Skill:\s*/i, "").slice(0, 80), thema: Number(thema) };
}


export const kategorieFarbe = (c) => (/^[0-9a-f]{3}([0-9a-f]{3})?$/i.test(String(c || "")) ? `#${c}` : "#8a949c");
