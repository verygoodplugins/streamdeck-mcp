import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const audioDir = join(root, "public", "audio");
const sampleRate = 22050;

mkdirSync(audioDir, { recursive: true });

const clamp = (value, min = -1, max = 1) => Math.max(min, Math.min(max, value));

const writeWav = (name, samples) => {
  const dataSize = samples.length * 2;
  const buffer = Buffer.alloc(44 + dataSize);

  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(36 + dataSize, 4);
  buffer.write("WAVE", 8);
  buffer.write("fmt ", 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36);
  buffer.writeUInt32LE(dataSize, 40);

  samples.forEach((sample, index) => {
    buffer.writeInt16LE(Math.round(clamp(sample) * 32767), 44 + index * 2);
  });

  writeFileSync(join(audioDir, name), buffer);
};

const render = (seconds, fn) => {
  const length = Math.floor(seconds * sampleRate);
  return Array.from({ length }, (_, index) => fn(index / sampleRate, index));
};

let seed = 424242;
const noise = () => {
  seed = (seed * 1664525 + 1013904223) >>> 0;
  return seed / 2147483648 - 1;
};

const sine = (freq, t) => Math.sin(Math.PI * 2 * freq * t);
const tri = (freq, t) => (2 / Math.PI) * Math.asin(sine(freq, t));
const envelope = (t, attack, release, length) => {
  const a = Math.min(1, t / attack);
  const r = Math.min(1, (length - t) / release);
  return clamp(Math.min(a, r), 0, 1);
};

const bed = render(45, (t) => {
  const bpm = 126;
  const beat = (t * bpm) / 60;
  const phase = beat % 1;
  const bar = Math.floor(beat / 4);
  const chords = [
    [55, 82.41, 98, 146.83],
    [65.41, 98, 123.47, 196],
    [73.42, 110, 146.83, 220],
    [61.74, 92.5, 123.47, 184.99],
  ];
  const chord = chords[bar % chords.length];
  const pad =
    chord.reduce((sum, freq, index) => {
      const detune = 1 + index * 0.004;
      return sum + tri(freq * detune, t) * (0.14 - index * 0.018);
    }, 0) * envelope(t, 1.8, 4.2, 45);
  const arpFreq = chord[Math.floor((beat * 2) % chord.length)] * 2;
  const arpGate = phase < 0.36 ? 1 - phase * 1.8 : 0;
  const arp = sine(arpFreq, t) * arpGate * 0.11;
  const kickPhase = phase;
  const kick =
    kickPhase < 0.18
      ? sine(46 - kickPhase * 130, kickPhase) * Math.exp(-kickPhase * 18) * 0.5
      : 0;
  const hat = beat % 0.5 < 0.05 ? noise() * 0.045 * Math.exp(-(beat % 0.5) * 28) : 0;
  const riser = t > 32 ? sine(220 + (t - 32) * 18, t) * ((t - 32) / 13) * 0.055 : 0;
  return (pad + arp + kick + hat + riser) * 0.72;
});

const uiClick = render(0.12, (t) => sine(1200, t) * envelope(t, 0.002, 0.08, 0.12) * 0.4);

const switchHit = render(0.32, (t) => {
  const body = sine(180, t) * envelope(t, 0.004, 0.23, 0.32) * 0.42;
  const snap = noise() * envelope(t, 0.001, 0.08, 0.12) * 0.24;
  return body + snap;
});

const whoosh = render(0.85, (t) => {
  const sweep = sine(280 + t * 1180, t) * 0.08;
  const air = noise() * (0.06 + t * 0.18);
  return (sweep + air) * envelope(t, 0.08, 0.2, 0.85);
});

const deepHit = render(0.9, (t) => {
  const thump = sine(62 - t * 22, t) * Math.exp(-t * 3.8) * 0.62;
  const shine = sine(880, t) * envelope(t, 0.01, 0.55, 0.9) * 0.1;
  return thump + shine;
});

const finalImpact = render(1.45, (t) => {
  const low = sine(48 - t * 8, t) * Math.exp(-t * 2.8) * 0.76;
  const mid = sine(144, t) * Math.exp(-t * 3.3) * 0.28;
  const burst = noise() * envelope(t, 0.004, 0.32, 0.5) * 0.24;
  return low + mid + burst;
});

writeWav("synth-bed.wav", bed);
writeWav("ui-click.wav", uiClick);
writeWav("switch-hit.wav", switchHit);
writeWav("whoosh.wav", whoosh);
writeWav("deep-hit.wav", deepHit);
writeWav("final-impact.wav", finalImpact);
