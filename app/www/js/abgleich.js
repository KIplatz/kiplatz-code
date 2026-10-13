// SPDX-License-Identifier: AGPL-3.0-or-later
import * as ak from "./abgleich-krypto.js";

import { name as fachName } from "./konten.js";

const zuordnung = () => "kiplatz." + fachName("abgleich-zuordnung");
export const PROJEKTE_ID = "0".repeat(32);

const zufallsId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), (x) => x.toString(16).padStart(2, "0")).join("");


export function inGemeinsam(g, titel) {
  return { titel, angeheftet: !!g.angeheftet, projekt: String(g.projekt || ""), farbe: String(g.farbe || ""), geaendert: Number(g.zeit || 0),
    nachrichten: g.nachrichten.map((n) => ({ ...n, zeit: Number(n.zeit || g.zeit || 0) })) };
}

export function ausGemeinsam(d, g) {
  g.eigenerTitel = String(d.titel || "").slice(0, 80);
  g.angeheftet = !!d.angeheftet;
  g.projekt = String(d.projekt || "").slice(0, 60);
  g.farbe = /^[a-z]{1,10}$/.test(String(d.farbe || "")) ? String(d.farbe) : "";
  g.nachrichten = (Array.isArray(d.nachrichten) ? d.nachrichten : []).filter((n) => n && (n.rolle === "user" || n.rolle === "assistant")).slice(-200)
    .map((n) => {
      const m = { ...n, text: String(n.text || "").slice(0, 20000) };

      if (m.mit != null) m.mit = String(m.mit).slice(0, 8000);
      if (m.anhaenge != null) m.anhaenge = (Array.isArray(m.anhaenge) ? m.anhaenge : []).slice(0, 3)
        .map((a) => ({ name: String(a?.name || "").slice(0, 120), zeichen: Number(a?.zeichen) || 0 }));
      return m;
    });
  g.zeit = Number(d.geaendert) || Date.now();
  return g;
}
async function fingerabdruck(g, titel) {
  const d = inGemeinsam(g, titel); delete d.geaendert;
  return ak.b64(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(d)))));
}

export class Abgleich {

  constructor({ holen, tresor, gespraeche, speichern, geraet, projekte = () => ({}), projekteSetzen = () => {} }) {
    Object.assign(this, { holen, tresor, gespraeche, speichern, geraet, projekte, projekteSetzen });
    this.laeuft = null;
    this.zuletzt = 0;
    this.fehler = "";
  }

  async _server(tat, felder = {}) { return this.holen("/abgleich", { body: { tat, ...felder }, geraet: this.geraet(), zeitlimit: 30000 }); }
  async _geheim() { return (await this.tresor.lesen("abgleich")) || {}; }
  async _geheimSchreiben(d) { await this.tresor.schreiben("abgleich", d); }
  _zuordnung() {
    try { const d = JSON.parse(localStorage.getItem(zuordnung()) || "{}"); return { zuordnung: d.zuordnung || {}, bekannt: d.bekannt || {}, stand: d.stand || {} }; }
    catch { return { zuordnung: {}, bekannt: {}, stand: {} }; }
  }
  _zuordnungSchreiben(z) { try { localStorage.setItem(zuordnung(), JSON.stringify(z)); } catch { } }
  async _privat(geheim) {
    if (!geheim.privat) { const g = await ak.neuesGeraet(); geheim.privat = g.privat; geheim.oeffentlich = g.oeffentlich; }
    return geheim;
  }
  async _k(geheim) { if (!geheim.k) throw new Error("Dieses Gerät ist für den Abgleich noch nicht zugelassen."); return ak.unb64(geheim.k); }

  async an() { return !!(await this._geheim()).an; }

  async stand() {
    const geheim = await this._geheim();
    if (!geheim.an) return { an: false };
    const s = await this._server("stand");
    return { an: true, eingerichtet: s.eingerichtet, zugelassen: !!s.mein_fach, wartet: !!s.meine_anfrage && !s.mein_fach,
      pruefzahl: geheim.oeffentlich ? await ak.pruefzahl(geheim.oeffentlich) : "",
      anfragen: await Promise.all(s.anfragen.map(async (q) => ({ kennung: q.kennung, name: q.name, pruefzahl: await ak.pruefzahl(q.oeffentlich) }))),
      wechsel_noetig: !!s.wechsel_noetig && !!s.mein_fach, belegt: s.belegt, grenze: s.grenze, gespraeche: Object.keys(s.bloecke).filter((b) => b !== PROJEKTE_ID).length,
      zuletzt: this.zuletzt, fehler: this.fehler };
  }


  async einschalten() {
    const geheim = await this._privat(await this._geheim());
    const s = await this._server("stand");
    const kennung = this.geraet().kennung;
    geheim.an = true;
    if (!s.eingerichtet) {
      const k = ak.neuerKontoschluessel(), r = ak.neuerWiederherstellungsschluessel();
      await this._server("einrichten", { fach: await ak.fachPacken(k, geheim.oeffentlich), oeffentlich: geheim.oeffentlich,
        siegel: await ak.siegel(k, kennung, geheim.oeffentlich), wiederherstellung: await ak.wiederherstellungPacken(k, r) });
      Object.assign(geheim, { k: ak.b64(k), version: 1 });
      await this._geheimSchreiben(geheim);
      return { wiederherstellung: r };
    }
    if (s.mein_fach) { await this._geheimSchreiben(geheim); return { schon: true }; }
    await this._server("anfrage", { oeffentlich: geheim.oeffentlich });
    await this._geheimSchreiben(geheim);
    return { pruefzahl: await ak.pruefzahl(geheim.oeffentlich) };
  }

  async zulassen(kennung) {
    const k = await this._k(await this._geheim());
    const s = await this._server("stand");
    const q = s.anfragen.find((x) => x.kennung === kennung);
    if (!q) throw new Error("Diese Anfrage gibt es nicht mehr. Am anderen Gerät noch einmal einschalten.");
    return this._server("zulassen", { kennung, fach: await ak.fachPacken(k, q.oeffentlich), siegel: await ak.siegel(k, kennung, q.oeffentlich), version: s.version });
  }
  async ablehnen(kennung) { return this._server("ablehnen", { kennung }); }

  async wiederherstellen(rText) {
    const geheim = await this._privat(await this._geheim());
    const w = await this._server("wiederherstellung");
    let k;
    try { k = await ak.wiederherstellungOeffnen(w.wiederherstellung, rText); }
    catch (e) { throw new Error(e instanceof ak.KryptoFehler ? "Dieser Wiederherstellungsschlüssel passt nicht." : e.message); }
    const kennung = this.geraet().kennung;
    await this._server("selbst", { fach: await ak.fachPacken(k, geheim.oeffentlich), oeffentlich: geheim.oeffentlich, siegel: await ak.siegel(k, kennung, geheim.oeffentlich), version: w.version });
    Object.assign(geheim, { an: true, k: ak.b64(k), version: w.version });
    await this._geheimSchreiben(geheim);
    return { ok: true };
  }


  async schluesselWechseln() {
    const geheim = await this._geheim();
    const kAlt = await this._k(geheim);
    const s = await this._server("stand");
    const erlaubt = new Set(s.geraete || []);
    const kNeu = ak.neuerKontoschluessel(), r = ak.neuerWiederherstellungsschluessel();
    const faecher = {};
    for (const [kennung, e] of Object.entries(s.schluessel || {})) {
      if (erlaubt.has(kennung) && await ak.siegelPruefen(kAlt, kennung, e.oeffentlich || {}, e.siegel || ""))
        faecher[kennung] = { fach: await ak.fachPacken(kNeu, e.oeffentlich), siegel: await ak.siegel(kNeu, kennung, e.oeffentlich) };
    }
    if (!faecher[this.geraet().kennung]) throw new Error("Der eigene Schlüssel am Server passt nicht. Bitte den Abgleich aus- und wieder einschalten.");
    const ids = Object.keys(s.bloecke), alt = {};
    for (let i = 0; i < ids.length; i += 50) Object.assign(alt, (await this._server("holen", { ids: ids.slice(i, i + 50) })).bloecke);
    const version = s.version + 1;
    await this._server("wechsel", { version, faecher, wiederherstellung: await ak.wiederherstellungPacken(kNeu, r) });
    Object.assign(geheim, { k: ak.b64(kNeu), version });
    await this._geheimSchreiben(geheim);
    const z = this._zuordnung();
    for (const [bid, daten] of Object.entries(alt)) {
      let inhalt;
      try { inhalt = await ak.blockEntschluesseln(kAlt, bid, daten); } catch { continue; }
      const v = Number(s.bloecke[bid].v) + 1;
      await this._server("schreiben", { id: bid, v, schluessel: version, daten: await ak.blockVerschluesseln(kNeu, bid, inhalt) });
      z.bekannt[bid] = v;
    }
    this._zuordnungSchreiben(z);
    return { wiederherstellung: r, geraete: Object.keys(faecher).length };
  }

  async ausschalten({ amServerLoeschen = false } = {}) {
    try { await this._server(amServerLoeschen ? "aus" : "verlassen"); } catch (e) { if (amServerLoeschen) throw e; }
    await this.tresor.loeschen("abgleich");
    localStorage.removeItem(zuordnung());
    return { an: false };
  }


  async _projekteAbgleichen(z, s, k, version) {
    const fp = async (m) => ak.b64(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(Object.keys(m).sort().map((n) => [n, m[n]]))))));
    let hier = this.projekte();
    let hierGeaendert = (await fp(hier)) !== z.stand[PROJEKTE_ID];
    const e = s.bloecke[PROJEKTE_ID];
    if (e && Number(e.v) > Number(z.bekannt[PROJEKTE_ID] || 0) && Number(e.schluessel) === version) {
      const daten = (await this._server("holen", { ids: [PROJEKTE_ID] })).bloecke[PROJEKTE_ID];
      let dort = null;
      try { dort = daten ? (await ak.blockEntschluesseln(k, PROJEKTE_ID, daten)).projekte || {} : {}; } catch { dort = null; }
      if (dort && typeof dort === "object") {
        this.projekteSetzen(hierGeaendert ? { ...dort, ...hier } : { ...dort });
        z.bekannt[PROJEKTE_ID] = Number(e.v);
        hier = this.projekte();
        z.stand[PROJEKTE_ID] = hierGeaendert ? "" : await fp(hier);
        hierGeaendert = z.stand[PROJEKTE_ID] !== await fp(hier);
      }
    }
    if (hierGeaendert && (Object.keys(hier).length || e)) {
      const v = Math.max(Number(s.bloecke[PROJEKTE_ID]?.v || 0) + 1, Date.now());
      await this._server("schreiben", { id: PROJEKTE_ID, v, schluessel: version, daten: await ak.blockVerschluesseln(k, PROJEKTE_ID, { projekte: hier, geaendert: v }) });
      z.bekannt[PROJEKTE_ID] = v; z.stand[PROJEKTE_ID] = await fp(hier);
    }
  }


  abgleichen() {
    if (!this.laeuft) this.laeuft = this._abgleichen().finally(() => { this.laeuft = null; });
    return this.laeuft;
  }

  async _abgleichen() {
    const geheim = await this._geheim();
    if (!geheim.an || !this.geraet()) return { an: false };
    const s = await this._server("stand");
    if (!s.mein_fach) return { an: true, zugelassen: false };
    if (!geheim.k || Number(geheim.version) !== Number(s.version)) {
      geheim.k = ak.b64(await ak.fachOeffnen(s.mein_fach, geheim.privat));
      geheim.version = s.version;
      await this._geheimSchreiben(geheim);
    }
    const k = ak.unb64(geheim.k), version = Number(s.version), G = this.gespraeche();
    const z = this._zuordnung();
    const bidVon = Object.fromEntries(Object.entries(z.zuordnung).map(([kennung, b]) => [b, kennung]));
    let geholt = 0, hochgeladen = 0, geloescht = 0;
    await this._projekteAbgleichen(z, s, k, version);

    const fehlt = Object.entries(s.bloecke).filter(([b, e]) => b !== PROJEKTE_ID && Number(e.v) > Number(z.bekannt[b] || 0) && Number(e.schluessel) === version).map(([b]) => b);
    for (let i = 0; i < fehlt.length; i += 50) {
      const r = await this._server("holen", { ids: fehlt.slice(i, i + 50) });
      for (const [bid, daten] of Object.entries(r.bloecke)) {
        let inhalt;
        try { inhalt = await ak.blockEntschluesseln(k, bid, daten); } catch { continue; }
        let g = G.liste.find((x) => x.kennung === bidVon[bid]);
        if (!g) {
          g = { kennung: bidVon[bid] || Array.from(crypto.getRandomValues(new Uint8Array(8)), (x) => x.toString(16).padStart(2, "0")).join(""), nachrichten: [], zeit: 0, angeheftet: false, eigenerTitel: "" };
          G.liste.push(g); z.zuordnung[g.kennung] = bid; bidVon[bid] = g.kennung;
        }
        ausGemeinsam(inhalt, g);
        z.bekannt[bid] = Number(s.bloecke[bid].v);
        z.stand[bid] = await fingerabdruck(g, G.titel(g));
        geholt++;
      }
    }

    for (const bid of Object.keys(z.bekannt).filter((b) => !(b in s.bloecke) && b !== PROJEKTE_ID)) {
      const kennung = bidVon[bid], g = G.liste.find((x) => x.kennung === kennung);
      const unveraendert = g && await fingerabdruck(g, G.titel(g)) === z.stand[bid];
      if (unveraendert) { G.loeschen(kennung); geloescht++; }
      if (kennung && (!g || unveraendert)) delete z.zuordnung[kennung];
      delete z.bekannt[bid]; delete z.stand[bid];
    }

    for (const [kennung, bid] of Object.entries(z.zuordnung)) {
      if (!G.liste.some((x) => x.kennung === kennung)) {
        if (bid in s.bloecke) await this._server("loeschen", { id: bid });
        delete z.zuordnung[kennung]; delete z.bekannt[bid]; delete z.stand[bid];
      }
    }

    for (const g of G.liste) {
      if (!g.nachrichten.length) continue;
      let bid = z.zuordnung[g.kennung];
      const fp = await fingerabdruck(g, G.titel(g));
      if (bid && z.stand[bid] === fp) continue;
      if (!bid) { bid = zufallsId(); z.zuordnung[g.kennung] = bid; }
      const v = Math.max(Number(s.bloecke[bid]?.v || 0) + 1, Number(g.zeit || 0));
      try { await this._server("schreiben", { id: bid, v, schluessel: version, daten: await ak.blockVerschluesseln(k, bid, inGemeinsam(g, G.titel(g))) }); }
      catch (e) { if (e.code === "ABGLEICH_VOLL" || e.code === "ABGLEICH_GROSS") { this.fehler = e.message; continue; } throw e; }
      z.bekannt[bid] = v; z.stand[bid] = fp;
      hochgeladen++;
    }
    this._zuordnungSchreiben(z);
    if (geholt || geloescht) this.speichern();
    this.zuletzt = Date.now();
    return { an: true, zugelassen: true, geholt, hochgeladen, geloescht };
  }
}
