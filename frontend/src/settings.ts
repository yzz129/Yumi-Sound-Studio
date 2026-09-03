export type TtsLanguage = "ZH" | "EN" | "JA" | "AR" | "ES";
export type EmotionMode = "voice" | "reference" | "vector";
export type SamplingPreset = "stable" | "natural" | "creative";
export type MusicEditMode = "remix" | "flow_edit" | "repaint";
export type MusicQuality = "fast" | "balanced" | "high";
export type AudioFormat = "wav" | "flac" | "mp3";

export interface TtsSettings {
  language: TtsLanguage;
  speed: number;
  emotionMode: EmotionMode;
  emotionStrength: number;
  emotionVector: number[];
  samplingPreset: SamplingPreset;
  doSample: boolean;
  temperature: number;
  topP: number;
  topK: number;
  numBeams: number;
  repetitionPenalty: number;
  segmentTokens: number;
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
  language: "ZH",
  speed: 1,
  emotionMode: "voice",
  emotionStrength: 0.65,
  emotionVector: [0, 0, 0, 0, 0, 0, 0, 0.35],
  samplingPreset: "natural",
  doSample: true,
  temperature: 0.8,
  topP: 0.8,
  topK: 30,
  numBeams: 3,
  repetitionPenalty: 10,
  segmentTokens: 120,
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

export const EMOTION_PRESETS = [
  { name: "平静", vector: [0, 0, 0, 0, 0, 0, 0, 0.75] },
  { name: "喜悦", vector: [0.8, 0, 0, 0, 0, 0, 0.25, 0.1] },
  { name: "愤怒", vector: [0, 0.85, 0, 0.15, 0.1, 0, 0, 0] },
  { name: "悲伤", vector: [0, 0, 0.72, 0.08, 0, 0.55, 0, 0.05] },
  { name: "紧张", vector: [0, 0.16, 0.08, 0.78, 0, 0.18, 0.08, 0] },
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

export const EMOTION_LABELS = ["喜", "怒", "哀", "惧", "厌恶", "低落", "惊喜", "平静"];
