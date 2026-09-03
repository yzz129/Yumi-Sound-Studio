import type { EngineStatus, JobState } from "./types";

export async function getStatus(): Promise<EngineStatus> {
  const response = await fetch("/api/status");
  if (!response.ok) throw new Error("无法读取模型状态");
  return response.json();
}

export async function startJob(mode: "tts" | "music", body: FormData): Promise<JobState> {
  const response = await fetch(`/api/${mode}`, { method: "POST", body });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "提交失败");
  return data;
}

export async function waitForJob(
  jobId: string,
  onUpdate: (job: JobState) => void,
): Promise<JobState> {
  for (;;) {
    const response = await fetch(`/api/jobs/${jobId}`);
    if (!response.ok) throw new Error("任务状态丢失");
    const job: JobState = await response.json();
    onUpdate(job);
    if (job.state === "completed") return job;
    if (job.state === "failed") throw new Error(job.error || "生成失败");
    await new Promise((resolve) => window.setTimeout(resolve, 1200));
  }
}

