// SPDX-License-Identifier: AGPL-3.0-or-later
import { adresse, lesen, stimmt, HelferFehler } from "./helfer.js";

let erkenner = null;
let laden = null;

function melden(nachricht) { self.postMessage(nachricht); }

async function bereitmachen(basis) {
  if (erkenner) return erkenner;
  if (laden) return laden;
  laden = (async () => {
    const dateien = {};
    const fortschritt = (datei) => (geladen, gesamt) => {
      dateien[datei] = { geladen, gesamt };
      let g = 0, t = 0;
      for (const d of Object.values(dateien)) { g += d.geladen; t += d.gesamt; }
      melden({ art: "fortschritt", geladen: g, gesamt: t });
    };


    const T = await import(await adresse("transformers/transformers.min.js", basis));
    const env = T.env;
    env.allowLocalModels = false;
    env.allowRemoteModels = true;
    env.remoteHost = basis + "modelle/";
    env.remotePathTemplate = "{model}/";
    env.useBrowserCache = true;
    env.useWasmCache = false;
    env.backends.onnx.wasm.numThreads = 1;
    env.backends.onnx.wasm.proxy = false;
    env.backends.onnx.wasm.wasmPaths = {
      mjs: await adresse("transformers/ort-wasm-simd-threaded.asyncify.mjs", basis),
      wasm: await adresse("transformers/ort-wasm-simd-threaded.asyncify.wasm", basis, fortschritt("wasm")),
    };

    env.fetch = async (url, optionen = {}) => {
      const u = String(url instanceof URL ? url.href : url?.url || url);
      if (!u.startsWith(basis)) throw new HelferFehler("Nur Helfer von kiplatz.at.");
      const pfad = u.slice(basis.length).split("?")[0];
      const kopf = new Headers(optionen.headers || {});
      const r = await fetch(u, { ...optionen, credentials: "omit", redirect: "error" });
      if (kopf.has("Range") || !r.ok) return r;
      const b = await lesen(r, fortschritt(pfad));
      if (!(await stimmt(pfad, b))) throw new HelferFehler(`${pfad} stimmt nicht mit der Prüfsumme in der App überein.`);
      return new Response(b, { status: 200, headers: { "Content-Type": r.headers.get("Content-Type") || "application/octet-stream", "Content-Length": String(b.byteLength) } });
    };
    erkenner = await T.pipeline("automatic-speech-recognition", "whisper-base", { device: "wasm", dtype: "q8" });
    return erkenner;
  })();
  try {
    return await laden;
  } catch (e) {
    laden = null;
    throw e;
  }
}

self.onmessage = async (e) => {
  const d = e.data || {};
  try {
    if (d.art === "laden") {
      await bereitmachen(d.basis);
      melden({ art: "bereit" });
    } else if (d.art === "erkennen") {
      const asr = await bereitmachen(d.basis);
      let ton = d.ton;
      const r = await asr(ton, { language: "german", task: "transcribe", chunk_length_s: 30, stride_length_s: 5 });
      ton = null;
      melden({ art: "text", text: String(r?.text || "").trim() });
    }
  } catch (err) {
    melden({ art: "fehler", text: String(err?.message || err).slice(0, 300) });
  }
};
