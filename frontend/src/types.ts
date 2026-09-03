export type Mode = "tts" | "music";

export interface EngineStatus {
  active: Mode | null;
  tts_ready: boolean;
  music_ready: boolean;
  busy: boolean;
}

export interface JobState {
  id: string;
  kind: Mode;
  state: "queued" | "running" | "completed" | "failed";
  message: string;
  result_url: string | null;
  result_urls?: string[];
  error: string | null;
}
