export type TtsMode = "clone" | "design" | "direction";
export type MusicEditMode = "remix" | "flow_edit" | "repaint";
export type MusicQuality = "fast" | "balanced" | "high";
export type AudioFormat = "wav" | "flac" | "mp3";

export interface TtsSettings {
  mode: TtsMode;
  refText: string;
  instruction: string;
  cfgScale: number;
  randomSeed: boolean;
  seed: string;
}

export interface MusicSettings {
  editMode: MusicEditMode;
  preserve: number;
  melodyRetention: number;
  duration: number;
  quality: MusicQuality;
  inferenceSteps: number;
  batchSize: number;
  randomSeed: boolean;
  seed: string;
  instrumental: boolean;
  lyrics: string;
  bpm: string;
  keyScale: string;
  timeSignature: string;
  outputFormat: AudioFormat;
  normalize: boolean;
  targetPeak: number;
  fadeIn: number;
  fadeOut: number;
  repaintStart: number;
  repaintEnd: number;
  repaintMode: "conservative" | "balanced" | "aggressive";
  repaintStrength: number;
  sourceCaption: string;
  flowMin: number;
  flowMax: number;
  flowSamples: number;
  noFsq: boolean;
  negativePrompt: string;
}

export const DEFAULT_TTS_SETTINGS: TtsSettings = {
  mode: "clone",
  refText: "",
  instruction: "",
  cfgScale: 4,
  randomSeed: true,
  seed: "42",
};

export const DEFAULT_MUSIC_SETTINGS: MusicSettings = {
  editMode: "remix",
  preserve: 0.9,
  melodyRetention: 0.2,
  duration: -1,
  quality: "balanced",
  inferenceSteps: 8,
  batchSize: 1,
  randomSeed: true,
  seed: "-1",
  instrumental: true,
  lyrics: "",
  bpm: "",
  keyScale: "",
  timeSignature: "",
  outputFormat: "wav",
  normalize: true,
  targetPeak: -1,
  fadeIn: 0,
  fadeOut: 0,
  repaintStart: 0,
  repaintEnd: -1,
  repaintMode: "balanced",
  repaintStrength: 0.5,
  sourceCaption: "",
  flowMin: 0,
  flowMax: 1,
  flowSamples: 1,
  noFsq: false,
  negativePrompt: "",
};

export const VOICE_PRESETS = [
  { name: "温柔讲述", instruction: "用温柔、自然的语气讲述，语速舒缓，停顿清晰。" },
  { name: "活泼开心", instruction: "用明亮、开心的语气说话，节奏轻快，情绪自然。" },
  { name: "克制悲伤", instruction: "用低落、克制的语气说话，语速稍慢，带有轻微叹息感。" },
  { name: "紧张急迫", instruction: "用紧张、急迫的语气说话，节奏稍快，吐字清晰。" },
] as const;

export const MUSIC_PRESETS = [
  { name: "戏曲急迫", caption: "低沉急迫的中国戏曲纯音乐，保持原节奏和主要旋律，突出快板与二胡，锣鼓克制有力，减少其他元素", preserve: 0.94, melodyRetention: 0.22 },
  { name: "极简保留", caption: "极简纯音乐改编，最大程度保持原速度、节奏骨架和旋律，只做轻微音色变化，避免增加多余乐器", preserve: 0.97, melodyRetention: 0.18 },
  { name: "电影紧张", caption: "低沉压迫的电影配乐，紧张渐进，克制的低频脉冲与少量弦乐，不要欢快，不要拥挤", preserve: 0.86, melodyRetention: 0.16 },
  { name: "国风悲情", caption: "克制悲情的国风纯音乐，二胡承担主情绪，少量古琴和低沉鼓点，保留原曲旋律走向", preserve: 0.9, melodyRetention: 0.2 },
  { name: "鼓点强化", caption: "保持原旋律与速度，强化清晰有力的鼓点和节奏层，其他乐器尽量不变，纯音乐", preserve: 0.93, melodyRetention: 0.2 },
  { name: "环境氛围", caption: "空间感宽阔的环境氛围音乐，柔和延展，减少旋律变化和突兀节奏，保持原曲情绪", preserve: 0.84, melodyRetention: 0.14 },
] as const;

export const QUALITY_STEPS: Record<MusicQuality, number> = {
  fast: 6,
  balanced: 8,
  high: 14,
};
