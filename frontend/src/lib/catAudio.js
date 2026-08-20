// 基于 Web Audio API 的零依赖程序化音效合成引擎
// Procedural audio synthesizer for mascot cat interactions

let audioCtx = null;
let soundEnabled = false;

// Initialize preference from localStorage
if (typeof window !== "undefined") {
  soundEnabled = localStorage.getItem("blog_cat_sound") === "true";
}

function getAudioContext() {
  if (typeof window === "undefined") return null;
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
}

export function isCatSoundEnabled() {
  return soundEnabled;
}

export function toggleCatSound(forcedState) {
  soundEnabled = typeof forcedState === "boolean" ? forcedState : !soundEnabled;
  if (typeof window !== "undefined") {
    localStorage.setItem("blog_cat_sound", soundEnabled ? "true" : "false");
  }
  if (soundEnabled) {
    getAudioContext();
    playPop();
  }
  return soundEnabled;
}

/**
 * 治愈软气泡点击音效 (Cute Soft Pop)
 */
export function playPop(frequency = 520) {
  if (!soundEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    const now = ctx.currentTime;

    osc.frequency.setValueAtTime(frequency * 0.8, now);
    osc.frequency.exponentialRampToValueAtTime(frequency * 1.5, now + 0.04);
    osc.frequency.exponentialRampToValueAtTime(frequency * 0.5, now + 0.12);

    gain.gain.setValueAtTime(0.12, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.12);
  } catch {
    // Audio context may be restricted by browser policy
  }
}

/**
 * 软萌小猫叫声 (Procedural Soft Meow)
 */
export function playCuteMeow() {
  if (!soundEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const filter = ctx.createBiquadFilter();

    osc.type = "triangle";
    // 猫叫的经典升降调曲线：580Hz -> 860Hz -> 620Hz
    osc.frequency.setValueAtTime(580, now);
    osc.frequency.linearRampToValueAtTime(860, now + 0.12);
    osc.frequency.exponentialRampToValueAtTime(620, now + 0.38);

    filter.type = "bandpass";
    filter.frequency.setValueAtTime(800, now);
    filter.Q.setValueAtTime(3, now);

    gain.gain.setValueAtTime(0.001, now);
    gain.gain.linearRampToValueAtTime(0.15, now + 0.08);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.38);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.38);
  } catch {}
}

/**
 * 木质键盘敲击音效 (Bongo Marimba Click)
 */
export function playBongoTap(isLeft = true) {
  if (!soundEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const now = ctx.currentTime;

    const baseFreq = isLeft ? 380 : 460;
    osc.type = "triangle";
    osc.frequency.setValueAtTime(baseFreq, now);
    osc.frequency.exponentialRampToValueAtTime(baseFreq * 0.4, now + 0.06);

    gain.gain.setValueAtTime(0.08, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.06);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.06);
  } catch {}
}

/**
 * 柔和低频猫咪呼噜声 (Purr Synthesizer)
 */
export function playPurr() {
  if (!soundEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const lfo = ctx.createOscillator();
    const lfoGain = ctx.createGain();
    const mainGain = ctx.createGain();
    const filter = ctx.createBiquadFilter();

    // 载波：低频 55Hz
    osc.type = "sine";
    osc.frequency.setValueAtTime(55, now);

    // 调制波：24Hz 颤音模拟声带震动
    lfo.type = "sine";
    lfo.frequency.setValueAtTime(24, now);
    lfoGain.gain.setValueAtTime(22, now);

    lfo.connect(osc.frequency);

    filter.type = "lowpass";
    filter.frequency.setValueAtTime(180, now);

    mainGain.gain.setValueAtTime(0.001, now);
    mainGain.gain.linearRampToValueAtTime(0.09, now + 0.15);
    mainGain.gain.exponentialRampToValueAtTime(0.001, now + 0.65);

    osc.connect(filter);
    filter.connect(mainGain);
    mainGain.connect(ctx.destination);

    lfo.start(now);
    osc.start(now);

    lfo.stop(now + 0.65);
    osc.stop(now + 0.65);
  } catch {}
}

/**
 * 灵光一闪清脆和弦音 (Eureka Chime)
 */
export function playEureka() {
  if (!soundEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const now = ctx.currentTime;
    const freqs = [523.25, 659.25, 783.99, 1046.5]; // C5, E5, G5, C6
    freqs.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const startTime = now + i * 0.05;

      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, startTime);

      gain.gain.setValueAtTime(0.001, startTime);
      gain.gain.linearRampToValueAtTime(0.08, startTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, startTime + 0.45);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(startTime);
      osc.stop(startTime + 0.45);
    });
  } catch {}
}

/**
 * 火箭升空呼啸风声 (Rocket Whoosh Wind)
 */
export function playRocketLaunch() {
  if (!soundEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(160, now);
    osc.frequency.exponentialRampToValueAtTime(980, now + 0.45);
    osc.frequency.exponentialRampToValueAtTime(180, now + 0.9);

    gain.gain.setValueAtTime(0.01, now);
    gain.gain.linearRampToValueAtTime(0.12, now + 0.25);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.9);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.9);
  } catch {}
}
