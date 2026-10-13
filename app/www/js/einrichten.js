// SPDX-License-Identifier: AGPL-3.0-or-later
export const WETTER = /\b(wetter\w*|regnet|schneit|wie warm|wie kalt|wie hei[ßs]|temperatur|grad|sonnig|gewitter|nebel)\b/i;
export const MIT_ORT = /\b(in|für|bei|um)\s+[A-ZÄÖÜ]|\b[Ww]etter\w*\s+(?:(?:heute|morgen|übermorgen)\s+)?[A-ZÄÖÜ]/;

export const NAEHE = /\b(in der n[äa]he|in meiner n[äa]he|n[äa]he von mir|in der umgebung|in meiner umgebung|im umkreis|hier in der gegend|bei mir in der gegend|hier im ort|bei uns im ort|in meinem ort)\b/i;


export function sauber(wert, max) {
  return String(wert || "").replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
}


export function mitOrt(text, ort) {
  const t = String(text || ""), o = sauber(ort, 60);
  if (!o || !t.trim()) return null;
  if (WETTER.test(t) && !MIT_ORT.test(t)) return t.replace(/[?.!\s]+$/, "") + ` in ${o}?`;
  if (NAEHE.test(t) && !t.toLocaleLowerCase("de").includes(o.toLocaleLowerCase("de"))) return t.trim() + (/[?.!]$/.test(t.trim()) ? "" : "?") + ` Ich wohne in ${o}.`;
  return null;
}
