// SPDX-License-Identifier: AGPL-3.0-or-later
import * as verlauf from "./verlauf.js";

const $ = (s) => document.querySelector(s);
function el(tag, attrs = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "onclick") e.onclick = v; else if (k === "text") e.textContent = v;
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const k of kinder) if (k != null) e.append(k);
  return e;
}
const mitglieder = (n) => (n === 1 ? "1 Mitglied" : `${n} Mitglieder`);

export function bestenlisteSeite({ holen, geraet, status }) {
  const inhalt = () => $("#bestenliste-inhalt");
  let offen = false, nr = 0;

  async function laden() {
    const g = geraet();
    const meine = ++nr;
    const [rang, teams, mein] = await Promise.all([
      holen("/rangliste", { geraet: g }).catch(() => null),
      holen("/teams", { geraet: g }).catch(() => null),
      g ? holen("/mein-team", { geraet: g }).catch((e) => (e.code === "KONTO_FEHLT" ? { ohne_konto: true } : null)) : Promise.resolve({ ohne_konto: true }),
    ]);
    if (meine !== nr || !offen) return;
    zeichnen(rang, teams, mein);
  }

  function zeichnen(rang, teams, mein) {
    const teile = [];


    const du = rang?.zeilen?.find((z) => z.du && (z.credits || z.antworten || z.abschnitte));
    teile.push(el("div", { class: "karte bl-platz" },
      du ? el("div", { class: "leise klein", text: "Dein Platz" }) : el("h3", { text: rang ? "Noch kein Platz" : "Dein Platz" }),
      du ? el("div", { class: "bl-platz-zahl", text: String(du.platz) }) : null,
      el("p", { class: "leise", text: !rang ? "Der Community-Server ist gerade nicht erreichbar."
        : du ? `von ${rang.anzahl} in der Community. ${du.antworten} Fragen beantwortet, ${du.abschnitte} Abschnitte erarbeitet, ${du.credits} Credits.${du.platz === 1 ? " Niemand hat mehr für andere getan." : ""}`
        : "Hier zählt, was deine PCs für andere erarbeiten. Mit dem KIplatz-Programm arbeitet dein PC mit, wenn er sonst nichts zu tun hat." }),
      rang && !du ? el("a", { class: "knopf", href: "https://kiplatz.at/rechenkraft-teilen/", target: "_blank", rel: "noopener noreferrer", text: "Programm für den PC" }) : null));

    teile.push(teamKarte(teams, mein));


    const tz = teams?.zeilen || [];
    teile.push(el("div", { class: "karte" },
      el("h3", { text: "Teams" }),
      el("p", { class: "leise klein", text: "Die Credits aller Mitglieder eines Teams zusammen." }),
      tz.length ? liste(tz.map((z) => ({ platz: z.platz, name: z.name, zusatz: "", unten: [z.dein_team ? "dein Team" : "", mitglieder(z.mitglieder), `${z.antworten} Fragen beantwortet`].filter(Boolean), credits: z.credits, hervor: z.dein_team })))
        : el("p", { class: "leise klein", text: teams ? "Noch gibt es kein Team. Gründe das erste." : "Der Community-Server ist gerade nicht erreichbar." })));


    const rz = rang?.zeilen || [];
    teile.push(el("div", { class: "karte" },
      el("h3", { text: "Alle, die für andere gearbeitet haben" }),
      el("p", { class: "leise klein", text: "Ein Credit je beantworteter Frage, je Bündel Abschnitte, je Prüfung. Wer keinen Haken bei „Mit Namen“ hat, steht als „Mitglied“ mit vier Zeichen da." }),
      rz.length ? liste(rz.map((z) => ({ platz: z.platz, name: z.name, zusatz: z.du ? "du" : "", unten: [z.team ? { name: z.team } : "", `${z.antworten} Fragen · ${z.abschnitte} Abschnitte`].filter(Boolean), credits: z.credits, hervor: z.du })))
        : el("p", { class: "leise klein", text: rang ? "Noch hat niemand für andere gearbeitet." : "Der Community-Server ist gerade nicht erreichbar." })));
    inhalt().replaceChildren(...teile);
  }


  function unten(teile) {
    return teile.flatMap((t, i) => [i ? " · " : null, typeof t === "string" ? el("span", { text: t }) : el("span", { text: t.name, translate: "no" })]);
  }

  function liste(zeilen) {
    return el("ol", { class: "bl-liste" }, ...zeilen.map((z) => el("li", { class: z.hervor ? "du" : null },
      el("span", { class: "bl-rang", text: String(z.platz) }),
      el("span", { class: "bl-wer" }, el("b", { text: z.name }), z.zusatz ? el("span", { class: "leise klein", text: ` (${z.zusatz})` }) : null, el("small", {}, ...unten(z.unten))),
      el("span", { class: "bl-credits" }, el("b", { text: String(z.credits) }), el("small", { text: "Credits" })))));
  }

  function teamKarte(teams, mein) {
    const k = el("div", { class: "karte", id: "bl-team-karte" }, el("h3", { text: "Dein Team" }));
    if (!mein) { k.append(el("p", { class: "leise klein", text: "Der Community-Server ist gerade nicht erreichbar." })); return k; }
    if (mein.ohne_konto) { k.append(el("p", { class: "leise klein", text: "Teams gibt es mit einem KIplatz-Konto. Melde dieses Handy mit deinem Konto an, unter „Konto und Einstellungen“ und „Konten“." })); return k; }
    const t = mein.team;
    const hinweis = t?.gesperrt ? `Der Admin hat euer Team gesperrt. Grund: ${t.gesperrt.grund || ""} Einspruch geht an melden@kiplatz.at.` : mein.hinweis || "";
    if (hinweis) k.append(el("p", { class: "info", role: "status", text: hinweis }));
    if (t) {
      const platz = teams?.dein_platz ? `Platz ${teams.dein_platz} von ${teams.anzahl} Teams` : "";
      k.append(el("p", { class: "bl-team-titel" }, el("b", { text: t.name }), el("small", { text: [platz, mitglieder(t.mitglieder)].filter(Boolean).join(" · ") })));
      if (!t.gesperrt) {
        k.append(el("p", { class: "klein" }, "Code zum Einladen: ", el("span", { class: "bl-code", id: "bl-code", text: t.code })),
          el("div", { class: "knopf-paar" },
            el("button", { class: "knopf", type: "button", text: "Code teilen", onclick: () => teilen(t) }),
            t.gegruendet ? el("button", { class: "knopf", type: "button", text: "Neuer Code", onclick: () => { if (confirm("Einen neuen Code machen? Der alte gilt danach nicht mehr.")) tun({ aktion: "code_neu" }); } }) : null),
          el("p", { class: "leise klein", text: "Schick den Code allen, die mitmachen sollen. Beitreten geht in der App und im Programm unter „Bestenliste“." }));
      }
      k.append(el("button", { class: "knopf breit", type: "button", text: "Team verlassen", onclick: () => { if (confirm("Das Team verlassen? Mit dem Code kannst du jederzeit wieder beitreten.")) tun({ aktion: "verlassen" }); } }));
    } else {
      const name = el("input", { id: "bl-team-name", maxlength: "40", placeholder: "z. B. Verein Muster", autocomplete: "off" });
      const code = el("input", { id: "bl-team-code", maxlength: "12", placeholder: "z. B. K7Q2-M9XA", autocomplete: "off", autocapitalize: "characters", spellcheck: "false" });
      k.append(el("p", { class: "leise klein", text: "Gemeinsam mit Verein, Firma, Schule oder Freunden: Die Arbeit aller Mitglieder zählt für das Team, und das Team bekommt einen Platz in der Team-Rangliste." }),
        el("label", { for: "bl-team-name", text: "Neues Team" }), name,
        el("button", { class: "knopf haupt breit", type: "button", text: "Team gründen", onclick: () => { const n = name.value.trim(); if (!n) { status("Bitte einen Namen für das Team eintragen."); return; } tun({ aktion: "anlegen", name: n }); } }),
        el("label", { for: "bl-team-code", text: "Code eines Teams" }), code,
        el("button", { class: "knopf breit", type: "button", text: "Mit Code beitreten", onclick: () => { const c = code.value.trim(); if (!c) { status("Bitte den Code des Teams eintragen."); return; } tun({ aktion: "beitreten", code: c }); } }));
    }
    const haken = el("input", { type: "checkbox", id: "bl-name-zeigen" });
    haken.checked = !!mein.name_oeffentlich;
    haken.onchange = () => tun({ aktion: "name", an: haken.checked });
    k.append(el("label", { class: "schalter bl-haken" }, haken, el("span", {}, "Mit Namen in der Bestenliste",
      el("small", { text: "Sonst stehst du dort als „Mitglied“ mit vier Zeichen, und dein Team steht nicht neben dir." }))));
    return k;
  }

  async function teilen(t) {
    const text = `Mach mit in unserem KIplatz-Team „${t.name}“: In der App oder im Programm unter „Bestenliste“ den Code ${t.code} eintragen. kiplatz.at`;
    try {
      if (navigator.share) { await navigator.share({ text }); return; }
      await navigator.clipboard.writeText(t.code); status("Code kopiert.");
    } catch (e) { if (e?.name !== "AbortError") status("Teilen ging nicht. Der Code steht oben zum Abschreiben."); }
  }

  async function tun(body) {
    for (const b of inhalt().querySelectorAll("#bl-team-karte button, #bl-team-karte input")) b.disabled = true;
    try { const r = await holen("/mein-team", { body, geraet: geraet() }); status(r.text || "Erledigt."); }
    catch (e) { status(e.message); }
    await laden();
  }


  function schliessen() { offen = false; $("#bestenliste").hidden = true; }
  function auf() {
    if (!offen) { offen = true; $("#bestenliste").hidden = false; verlauf.auf("bestenliste", schliessen); }
    inhalt().replaceChildren(el("p", { class: "leise mitte", text: "Einen Moment …" }));
    $("#bestenliste-titel").focus({ preventScroll: true });
    laden();
  }
  function zu() { if (!verlauf.schliessen("bestenliste")) schliessen(); }
  function zurueck() { if (!verlauf.zurueck("bestenliste")) schliessen(); }

  $("#btn-bestenliste").onclick = auf;
  $("#btn-bestenliste-zurueck").onclick = zurueck;
  return { auf, zu, zurueck, offen: () => offen };
}
