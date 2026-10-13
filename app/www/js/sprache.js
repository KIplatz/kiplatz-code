// SPDX-License-Identifier: AGPL-3.0-or-later
export const MAX_S = 90;
export const RATE = 16000;
export const GROESSE_MB = 107;

import { helferBasis } from "./helfer.js";
export { helferBasis };


export function aufMono16k(kanaele, rate) {
  const n = kanaele[0]?.length || 0;
  const mono = new Float32Array(n);
  for (const k of kanaele) for (let i = 0; i < n; i++) mono[i] += k[i] / kanaele.length;
  if (rate === RATE) return mono;
  const verhaeltnis = rate / RATE;
  const aus = new Float32Array(Math.floor(n / verhaeltnis));
  for (let i = 0; i < aus.length; i++) {

    const a = Math.floor(i * verhaeltnis), b = Math.min(n, Math.floor((i + 1) * verhaeltnis));
    let s = 0;
    for (let j = a; j < b; j++) s += mono[j];
    aus[i] = b > a ? s / (b - a) : mono[a] || 0;
  }
  return aus;
}


export function anhaengen(bisher, neu) {
  neu = String(neu || "").trim();
  if (!neu) return bisher;
  return bisher && !/\s$/.test(bisher) ? bisher + " " + neu : bisher + neu;
}


export class Sprechen {
  constructor({ melden, text }) {
    this.melden = melden;
    this.textFertig = text;
    this.phase = "aus";
    this.worker = null;
    this.bereit = false;
    this.aufnahme = null;
  }

  _worker() {
    if (this.worker) return this.worker;
    this.worker = new Worker(new URL("./sprache-worker.js", import.meta.url), { type: "module" });
    this.worker.onmessage = (e) => this._antwort(e.data || {});
    this.worker.onerror = () => this._fehler("Die Spracherkennung ließ sich nicht starten.");
    return this.worker;
  }

  _antwort(d) {
    if (d.art === "fortschritt") {
      const mb = (x) => Math.round(x / 1e6);
      if (this.phase === "holen" || this.phase === "erkennen") this.melden(this.phase, `Die Spracherkennung wird geholt: ${mb(d.geladen)} von ${mb(d.gesamt) || GROESSE_MB} MB`);
    } else if (d.art === "bereit") {
      this.bereit = true;
      if (this.phase === "holen") { this.phase = "bereit"; this.melden("bereit", "Bereit. Mikrofon drücken und sprechen."); }
    } else if (d.art === "text") {
      this.bereit = true;
      this.phase = "aus";
      if (d.text) { this.textFertig(d.text); this.melden("aus", ""); }
      else this.melden("aus", "Da war nichts zu verstehen. Mikrofon drücken, sprechen, noch einmal drücken.");
    } else if (d.art === "fehler") {
      this._fehler("Das Verstehen hat nicht geklappt: " + d.text);
    }
  }

  _fehler(text) { this._aufraeumen(); this.phase = "fehler"; this.melden("fehler", text); }


  holen() {
    if (this.bereit) return;
    this.phase = "holen";
    this.melden("holen", `Die Spracherkennung wird geholt (${GROESSE_MB} MB, nur beim ersten Mal) …`);
    this._worker().postMessage({ art: "laden", basis: helferBasis() });
  }


  async druecken() {
    if (this.phase === "aufnahme") return this.beenden();
    if (this.phase === "erkennen") return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      return this._fehler("Dieser Browser kann nicht aufnehmen. In Safari oder Chrome am Handy geht es.");
    }
    let strom;
    try {
      strom = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    } catch (e) {
      return this._fehler(e?.name === "NotAllowedError"
        ? "Das Mikrofon ist für KIplatz nicht erlaubt. In den Einstellungen des Handys unter Safari (oder der App) → Mikrofon erlauben."
        : "Kein Mikrofon gefunden.");
    }
    if (!this.bereit) this._worker().postMessage({ art: "laden", basis: helferBasis() });
    const stuecke = [];
    const rec = new MediaRecorder(strom);
    rec.ondataavailable = (e) => { if (e.data?.size) stuecke.push(e.data); };
    const beginn = Date.now();
    this.aufnahme = { strom, rec, stuecke, beginn, verwerfen: false, uhr: setInterval(() => {
      const s = Math.round((Date.now() - beginn) / 1000);
      this.melden("aufnahme", `Aufnahme läuft, ${s} s. Noch einmal auf das Mikrofon beendet sie.`, s);
      if (s >= MAX_S) this.beenden();
    }, 500) };
    rec.onstop = () => this._fertig();
    rec.start();
    this.phase = "aufnahme";
    this.melden("aufnahme", "Aufnahme läuft, 0 s. Noch einmal auf das Mikrofon beendet sie.", 0);
  }

  beenden() {
    const a = this.aufnahme;
    if (!a || a.rec.state === "inactive") return;
    clearInterval(a.uhr);
    a.rec.stop();
    a.strom.getTracks().forEach((t) => t.stop());
  }


  verwerfen() {
    if (!this.aufnahme) return;
    this.aufnahme.verwerfen = true;
    this.beenden();
    this.melden("aus", "Aufnahme verworfen.");
  }

  _aufraeumen() {
    const a = this.aufnahme;
    if (!a) return;
    clearInterval(a.uhr);
    try { if (a.rec.state !== "inactive") a.rec.stop(); } catch { }
    a.strom.getTracks().forEach((t) => t.stop());
    this.aufnahme = null;
  }

  async _fertig() {
    const a = this.aufnahme;
    this.aufnahme = null;
    if (!a || a.verwerfen) { this.phase = "aus"; return; }
    this.phase = "erkennen";
    this.melden("erkennen", "Wird verstanden …");
    try {
      let blob = new Blob(a.stuecke, { type: a.rec.mimeType || "audio/mp4" });
      a.stuecke.length = 0;
      const ctx = new (globalThis.AudioContext || globalThis.webkitAudioContext)();
      const puffer = await ctx.decodeAudioData(await blob.arrayBuffer());
      blob = null;
      ctx.close();
      const kanaele = [];
      for (let i = 0; i < puffer.numberOfChannels; i++) kanaele.push(puffer.getChannelData(i));
      const ton = aufMono16k(kanaele, puffer.sampleRate);
      if (ton.length < RATE * 0.4) { this.phase = "aus"; return this.melden("aus", "Da war nichts zu verstehen. Mikrofon drücken, sprechen, noch einmal drücken."); }
      if (!this.bereit) this.melden("erkennen", "Die Spracherkennung wird geholt …");
      this._worker().postMessage({ art: "erkennen", basis: helferBasis(), ton }, [ton.buffer]);
    } catch {
      this._fehler("Die Aufnahme ließ sich nicht lesen. Bitte noch einmal.");
    }
  }
}
