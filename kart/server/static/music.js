/* GoKart dash music: an original chiptune loop under the game sounds. WebAudio synthesis only, like
   sound.js: no audio files, nothing from any game. Kart driver page only (the pit stays quiet).

   GKMusic.init({ sound: GKSound, volume: 0-1, enabled: bool, onchange: fn })
   GKMusic.setTheme("race" | "idle" | null)   null = silence (race lights, the finish fanfare)
   GKMusic.setTempo(scale)                    1.0 normal; a boost pushes it up, a slow pulls it down (eased)
   GKMusic.duck(level, ms)                    dip under a sound effect (GKSound's onplay hook calls it)
   GKMusic.setMuted(b) / .muted (localStorage "gk_music"), .enabled, .theme, .playing
   GKMusic.selfTest(seconds) -> Promise<{peak, notes}>   renders the race loop offline (no speakers needed)

   Themes are 16th-note step patterns (one string per bar, 16 tokens: "A4" note, "." rest, "-" hold;
   drums "x"/"X"). Voices: lead = filtered square, bass = triangle+saw, arp = quiet square, kick/snare/hat
   synthesized. Notes are scheduled 140 ms ahead from a 30 ms timer (the usual two-clocks pattern), so a
   busy main thread (map redraws on the Pi 3 B) does not stutter the beat. The music plays into GKSound's
   output chain, so the first touch that unlocks sound unlocks the music too. */
"use strict";
const GKMusic = (() => {
  const NOTE = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  const midi = (tok) => {
    const m = /^([A-G])([#b]?)(-?\d)$/.exec(tok);
    return m ? 12 * (Number(m[3]) + 1) + NOTE[m[1]] + (m[2] === "#" ? 1 : m[2] === "b" ? -1 : 0) : null;
  };
  const hz = (n) => 440 * Math.pow(2, (n - 69) / 12);
  const rep = (bar, n) => Array(n).fill(bar);
  function parse(bars) {                       // -> [{step, midi, len}] (len in 16ths; "-" extends the note)
    const ev = []; let last = null;
    bars.forEach((bar, b) => bar.trim().split(/\s+/).forEach((tok, i) => {
      if (tok === "-") { if (last) last.len++; return; }
      last = null;
      if (tok === ".") return;
      const n = midi(tok);
      if (n === null) return;
      last = { step: b * 16 + i, midi: n, len: 1 }; ev.push(last);
    }));
    return ev;
  }
  function hits(bars) {
    const ev = [];
    bars.forEach((bar, b) => bar.trim().split(/\s+/).forEach((tok, i) => { if (tok === "x" || tok === "X") ev.push({ step: b * 16 + i, acc: tok === "X" }); }));
    return ev;
  }
  const THEMES = {
    // RACE: A minor, 142 bpm, 8 bars. Driving 8th-note bass under a two-phrase lead, chord arps, full kit.
    race: {
      bpm: 142, bars: 8,
      lead: parse([
        "A4 . . A4 . . C5 . E5 . . D5 . C5 . .",
        "A4 . . A4 . . C5 . E5 . G5 . E5 - . .",
        "F4 . . F4 . . A4 . C5 . . A4 . F4 . .",
        "F4 . . G4 . . A4 . C5 . D5 . C5 - . .",
        "G4 . . G4 . . B4 . D5 . . B4 . G4 . .",
        "G4 . . G4 . . B4 . D5 . F5 . D5 - . .",
        "E4 . . E4 . . G#4 . B4 . . G#4 . E4 . .",
        "E4 . . G#4 . . B4 . D5 . E5 - - - . .",
      ]),
      bass: parse([
        "A2 . A2 . A3 . A2 . A2 . A3 . A2 . A3 .", "A2 . A2 . A3 . A2 . A2 . A3 . A2 . G2 .",
        "F2 . F2 . F3 . F2 . F2 . F3 . F2 . F3 .", "F2 . F2 . F3 . F2 . F2 . F3 . F2 . E2 .",
        "G2 . G2 . G3 . G2 . G2 . G3 . G2 . G3 .", "G2 . G2 . G3 . G2 . G2 . G3 . G2 . F2 .",
        "E2 . E2 . E3 . E2 . E2 . E3 . E2 . E3 .", "E2 . E2 . E3 . E2 . E2 . E3 . G2 . G#2 .",
      ]),
      arp: parse([
        ...rep("A4 C5 E5 A5 A4 C5 E5 A5 A4 C5 E5 A5 A4 C5 E5 A5", 2),
        ...rep("F4 A4 C5 F5 F4 A4 C5 F5 F4 A4 C5 F5 F4 A4 C5 F5", 2),
        ...rep("G4 B4 D5 G5 G4 B4 D5 G5 G4 B4 D5 G5 G4 B4 D5 G5", 2),
        ...rep("E4 G#4 B4 E5 E4 G#4 B4 E5 E4 G#4 B4 E5 E4 G#4 B4 E5", 2),
      ]),
      kick: hits([...rep("X . . . x . . . X . . . x . x .", 7), "X . . . x . . . X . . . x . x x"]),
      snare: hits([...rep(". . . . x . . . . . . . x . . .", 7), ". . . . x . . . . . . . x . x x"]),
      hat: hits(rep("x . x . x . x . x . x . x . x x", 8)),
    },
    // IDLE: C major, 96 bpm, 4 bars. Sparse triangle lead over half-note bass and soft 8th arps; light kit.
    idle: {
      bpm: 96, bars: 4,
      lead: parse([
        "E5 . . . G5 . . . C6 - - - . . . .",
        "D5 . . . . . G5 . . . . . . . . .",
        "E5 . . . G5 . . . A5 - . . G5 . . .",
        ". . . . E5 . . . D5 - - - . . . .",
      ]),
      bass: parse([
        "C3 - - - - - - - C3 - - - - - - -", "G2 - - - - - - - G2 - - - - - - -",
        "A2 - - - - - - - A2 - - - - - - -", "G2 - - - - - - - G2 - - - - B2 - - -",
      ]),
      arp: parse([
        "C4 . E4 . G4 . E4 . C4 . E4 . G4 . E4 .", "B3 . D4 . G4 . D4 . B3 . D4 . G4 . D4 .",
        "A3 . C4 . E4 . C4 . A3 . C4 . E4 . C4 .", "B3 . D4 . G4 . D4 . B3 . D4 . G4 . D4 .",
      ]),
      kick: hits(rep("x . . . . . . . x . . . . . . .", 4)),
      snare: hits([]),
      hat: hits(rep("x . . . x . . . x . . . x . . .", 4)),
    },
  };
  Object.values(THEMES).forEach((th) => {      // index every track by step for the scheduler
    th.len = th.bars * 16;
    th.at = {};
    for (const k of ["lead", "bass", "arp", "kick", "snare", "hat"]) {
      th.at[k] = Array.from({ length: th.len }, () => []);
      th[k].forEach((e) => { if (e.step < th.len) th.at[k][e.step].push(e); });
    }
  });

  // ---- voices (ctx, bus explicit so the offline self-test can use them too) ---------------------------
  const noiseBufs = new WeakMap();
  function noise(ctx) {
    let b = noiseBufs.get(ctx);
    if (!b) {
      const n = ctx.sampleRate; b = ctx.createBuffer(1, n, n);
      const d = b.getChannelData(0);
      for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
      noiseBufs.set(ctx, b);
    }
    return b;
  }
  function env(g, t, vol, dur, rel) {
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + 0.008);
    g.gain.setValueAtTime(vol, t + Math.max(0.008, dur - rel));
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  }
  function lead(ctx, bus, t, n, dur) {
    const o = ctx.createOscillator(), f = ctx.createBiquadFilter(), g = ctx.createGain();
    o.type = "square"; o.frequency.value = hz(n);
    f.type = "lowpass"; f.frequency.setValueAtTime(2800, t); f.frequency.exponentialRampToValueAtTime(1000, t + dur);
    env(g, t, 0.17, dur, 0.05);
    o.connect(f); f.connect(g); g.connect(bus); o.start(t); o.stop(t + dur + 0.02);
  }
  function bass(ctx, bus, t, n, dur) {
    const o = ctx.createOscillator(), o2 = ctx.createOscillator(), f = ctx.createBiquadFilter(), g = ctx.createGain(), g2 = ctx.createGain();
    o.type = "triangle"; o.frequency.value = hz(n);
    o2.type = "sawtooth"; o2.frequency.value = hz(n); g2.gain.value = 0.35;
    f.type = "lowpass"; f.frequency.value = 520;
    env(g, t, 0.34, dur, 0.04);
    o.connect(f); o2.connect(g2); g2.connect(f); f.connect(g); g.connect(bus);
    o.start(t); o2.start(t); o.stop(t + dur + 0.02); o2.stop(t + dur + 0.02);
  }
  function arp(ctx, bus, t, n, dur) {
    const o = ctx.createOscillator(), f = ctx.createBiquadFilter(), g = ctx.createGain();
    o.type = "square"; o.frequency.value = hz(n);
    f.type = "lowpass"; f.frequency.value = 1900;
    env(g, t, 0.045, Math.min(dur, 0.09), 0.03);
    o.connect(f); f.connect(g); g.connect(bus); o.start(t); o.stop(t + Math.min(dur, 0.09) + 0.02);
  }
  function kick(ctx, bus, t, acc) {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = "sine"; o.frequency.setValueAtTime(150, t); o.frequency.exponentialRampToValueAtTime(42, t + 0.12);
    env(g, t, acc ? 0.7 : 0.55, 0.15, 0.08);
    o.connect(g); g.connect(bus); o.start(t); o.stop(t + 0.17);
  }
  function snare(ctx, bus, t, acc) {
    const s = ctx.createBufferSource(), bp = ctx.createBiquadFilter(), g = ctx.createGain(), o = ctx.createOscillator(), g2 = ctx.createGain();
    s.buffer = noise(ctx); bp.type = "bandpass"; bp.frequency.value = 1900; bp.Q.value = 0.7;
    env(g, t, acc ? 0.36 : 0.28, 0.13, 0.09);
    o.type = "sine"; o.frequency.setValueAtTime(190, t); o.frequency.exponentialRampToValueAtTime(110, t + 0.08);
    env(g2, t, 0.25, 0.09, 0.05);
    s.connect(bp); bp.connect(g); g.connect(bus); o.connect(g2); g2.connect(bus);
    s.start(t); s.stop(t + 0.15); o.start(t); o.stop(t + 0.11);
  }
  function hat(ctx, bus, t, acc) {
    const s = ctx.createBufferSource(), hp = ctx.createBiquadFilter(), g = ctx.createGain();
    s.buffer = noise(ctx); hp.type = "highpass"; hp.frequency.value = 7200;
    env(g, t, acc ? 0.14 : 0.09, 0.035, 0.02);
    s.connect(hp); hp.connect(g); g.connect(bus); s.start(t); s.stop(t + 0.05);
  }
  function scheduleStep(ctx, bus, th, i, t, stepS) {
    th.at.lead[i].forEach((e) => lead(ctx, bus, t, e.midi, e.len * stepS * 0.92));
    th.at.bass[i].forEach((e) => bass(ctx, bus, t, e.midi, e.len * stepS * 0.9));
    th.at.arp[i].forEach((e) => arp(ctx, bus, t, e.midi, e.len * stepS));
    th.at.kick[i].forEach((e) => kick(ctx, bus, t, e.acc));
    th.at.snare[i].forEach((e) => snare(ctx, bus, t, e.acc));
    th.at.hat[i].forEach((e) => hat(ctx, bus, t, e.acc));
  }

  // ---- live player ------------------------------------------------------------------------------------
  const S = {
    snd: null, vol: 0.5, enabled: true, onchange: null, theme: null, th: null,
    ctx: null, bus: null, duckG: null, timer: null, step: 0, nextT: 0, tempo: 1, tempoTarget: 1,
    muted: (() => { try { return localStorage.getItem("gk_music") === "1"; } catch (e) { return false; } })(),
  };
  const level = () => Math.max(0, Math.min(1, S.vol)) * 0.42;      // the effects stay on top
  function changed() { if (S.onchange) try { S.onchange(); } catch (e) { /* ui only */ } }
  function bus() {
    if (!S.snd) return null;
    const ctx = S.snd.context();
    if (!ctx) return null;
    if (!S.bus || S.ctx !== ctx) {
      S.ctx = ctx;
      S.bus = ctx.createGain(); S.bus.gain.value = 0.0001;
      S.duckG = ctx.createGain(); S.duckG.gain.value = 1;
      S.bus.connect(S.duckG); S.duckG.connect(S.snd.output());
    }
    return ctx;
  }
  const stepS = () => 60 / (S.th.bpm * 4) / S.tempo;
  function tick() {
    if (!S.th || !S.ctx || S.ctx.state !== "running") return;
    const now = S.ctx.currentTime;
    if (S.nextT < now - 0.5) S.nextT = now + 0.05;            // the page was paused: do not burst-schedule the gap
    const horizon = now + 0.14;
    while (S.nextT < horizon) {
      S.tempo += (S.tempoTarget - S.tempo) * 0.06;            // eased tempo changes (boost up, slow down)
      scheduleStep(S.ctx, S.bus, S.th, S.step, S.nextT, stepS());
      S.nextT += stepS();
      S.step = (S.step + 1) % S.th.len;
    }
  }
  function ramp(g, v, s) {
    const t = S.ctx.currentTime;
    g.gain.cancelScheduledValues(t); g.gain.setValueAtTime(Math.max(0.0001, g.gain.value), t);
    g.gain.exponentialRampToValueAtTime(Math.max(0.0001, v), t + s);
  }
  function start(name) {
    const ctx = bus();
    if (!ctx) return;
    S.th = THEMES[name]; S.step = 0; S.nextT = ctx.currentTime + 0.05;
    ramp(S.bus, level(), 0.25);
    if (!S.timer) S.timer = setInterval(tick, 30);
  }
  function stop() {
    if (S.timer) { clearInterval(S.timer); S.timer = null; }
    if (S.bus) ramp(S.bus, 0.0001, 0.2);
    S.th = null;
  }
  const wants = () => S.enabled && !S.muted && !!S.theme;
  function apply() { if (wants()) { if (!S.th || S.th !== THEMES[S.theme]) start(S.theme); } else if (S.th) stop(); }

  return {
    THEMES: Object.keys(THEMES),
    init(o) {
      if (o.sound) S.snd = o.sound;
      if (o.volume !== undefined && o.volume !== null && !Number.isNaN(Number(o.volume))) S.vol = Number(o.volume);
      if (o.enabled !== undefined) S.enabled = o.enabled !== false;
      if (o.onchange) S.onchange = o.onchange;
      if (S.bus && S.th) ramp(S.bus, level(), 0.1);
      apply(); changed();
    },
    get muted() { return S.muted; },
    get enabled() { return S.enabled; },
    get theme() { return S.theme; },
    get playing() { return !!S.th && !!S.ctx && S.ctx.state === "running"; },
    setMuted(m) {
      S.muted = !!m;
      try { localStorage.setItem("gk_music", S.muted ? "1" : "0"); } catch (e) { /* per-display */ }
      apply(); changed();
    },
    setTheme(name) {
      if (name && !THEMES[name]) name = null;
      if (name === S.theme) { apply(); return; }
      S.theme = name; apply();
    },
    setTempo(x) { S.tempoTarget = Math.max(0.5, Math.min(1.6, Number(x) || 1)); },
    duck(lvl, ms) {
      if (!S.duckG || !S.ctx || !S.th) return;
      const t = S.ctx.currentTime, g = S.duckG.gain;
      g.cancelScheduledValues(t); g.setValueAtTime(g.value, t);
      g.linearRampToValueAtTime(Math.max(0.05, lvl), t + 0.02);
      g.linearRampToValueAtTime(1, t + 0.02 + Math.max(0.1, ms) / 1000);
    },
    poke() { tick(); },                           // tests / tabs that throttle timers
    selfTest(seconds) {                           // offline render of the race loop: {peak, notes}
      const secs = Math.max(0.5, Math.min(10, seconds || 2));
      const AC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
      const ctx = new AC(2, Math.round(44100 * secs), 44100), out = ctx.createGain();
      out.gain.value = 0.42; out.connect(ctx.destination);
      const th = THEMES.race, s = 60 / (th.bpm * 4);
      let notes = 0;
      for (let i = 0, t = 0.02; t < secs; i = (i + 1) % th.len, t += s) {
        scheduleStep(ctx, out, th, i, t, s);
        notes += th.at.lead[i].length + th.at.bass[i].length + th.at.kick[i].length;
      }
      return ctx.startRendering().then((buf) => {
        let peak = 0;
        const d = buf.getChannelData(0);
        for (let i = 0; i < d.length; i += 7) peak = Math.max(peak, Math.abs(d[i]));
        return { peak: Math.round(peak * 1000) / 1000, notes };
      });
    },
  };
})();
