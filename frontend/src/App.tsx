import { Cloudy, Leaf, LoaderCircle, Mic2, Music2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { MusicAdvancedSettings, MusicPresetStrip, TtsAdvancedSettings } from "./AdvancedSettings";
import { getStatus, startJob, waitForJob } from "./api";
import AgentPet, { type MusicPlan } from "./AgentPet";
import { PrivacyNote, RangeControl, UploadField } from "./components";
import ResultPanel from "./ResultPanel";
import { DEFAULT_MUSIC_SETTINGS, DEFAULT_TTS_SETTINGS, type MusicSettings, type TtsSettings } from "./settings";
import type { EngineStatus, JobState, Mode } from "./types";

const initialStatus: EngineStatus = { active: null, tts_ready: false, music_ready: false, busy: false };

export default function App() {
  const [mode, setMode] = useState<Mode>("tts");
  const [status, setStatus] = useState(initialStatus);
  const [voiceFile, setVoiceFile] = useState<File | null>(null);
  const [emotionReference, setEmotionReference] = useState<File | null>(null);
  const [musicFile, setMusicFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [caption, setCaption] = useState("保持原节奏与旋律走向，原声降低，加入更多快板、二胡和少量锣鼓");
  const [ttsSettings, setTtsSettings] = useState<TtsSettings>(DEFAULT_TTS_SETTINGS);
  const [musicSettings, setMusicSettings] = useState<MusicSettings>(DEFAULT_MUSIC_SETTINGS);
  const [job, setJob] = useState<JobState | null>(null);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Record<Mode, string[]>>({ tts: [], music: [] });
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);

  useEffect(() => {
    getStatus().then(setStatus).catch(() => undefined);
    const timer = window.setInterval(() => getStatus().then(setStatus).catch(() => undefined), 5000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!musicFile) {
      setSourceUrl(null);
      return undefined;
    }
    const url = URL.createObjectURL(musicFile);
    setSourceUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [musicFile]);

  const working = job?.state === "queued" || job?.state === "running";

  async function submit(modeToRun: Mode, override?: MusicPlan): Promise<boolean> {
    setError("");
    const body = new FormData();
    if (modeToRun === "tts") {
      if (!voiceFile || !text.trim()) {
        setError("先上传参考声音，再输入要说的话吧。");
        return false;
      }
      if (ttsSettings.emotionMode === "reference" && !emotionReference) {
        setError("选择了情绪参考模式，请再上传一段情绪参考声音。");
        return false;
      }
      body.append("reference", voiceFile);
      if (emotionReference) body.append("emotion_reference", emotionReference);
      body.append("text", text.trim());
      appendFields(body, {
        language: ttsSettings.language,
        speed: ttsSettings.speed,
        emotion_mode: ttsSettings.emotionMode,
        emotion: ttsSettings.emotionStrength,
        emotion_vector: JSON.stringify(ttsSettings.emotionVector),
        do_sample: ttsSettings.doSample,
        top_p: ttsSettings.topP,
        top_k: ttsSettings.topK,
        temperature: ttsSettings.temperature,
        num_beams: ttsSettings.numBeams,
        repetition_penalty: ttsSettings.repetitionPenalty,
        segment_tokens: ttsSettings.segmentTokens,
      });
    } else {
      const resolvedCaption = override?.caption || caption;
      if (!musicFile || !resolvedCaption.trim()) {
        setError("先上传原音乐，再告诉我想怎么改吧。");
        setMode("music");
        return false;
      }
      const effective: MusicSettings = {
        ...musicSettings,
        ...(override?.preserve !== undefined ? { preserve: override.preserve } : {}),
        ...(override?.melodyRetention !== undefined ? { melodyRetention: override.melodyRetention } : {}),
        ...(override?.duration !== undefined ? { duration: override.duration } : {}),
        ...(override?.editMode ? { editMode: override.editMode } : {}),
        ...(override?.quality ? { quality: override.quality, inferenceSteps: override.inferenceSteps ?? musicSettings.inferenceSteps } : {}),
        ...(override?.batchSize ? { batchSize: override.batchSize } : {}),
      };
      if (effective.editMode === "repaint" && effective.repaintEnd >= 0 && effective.repaintEnd <= effective.repaintStart) {
        setError("局部重绘的结束时间需要晚于开始时间。");
        return false;
      }
      body.append("source", musicFile);
      appendFields(body, {
        caption: resolvedCaption.trim(), edit_mode: effective.editMode, preserve: effective.preserve,
        melody_retention: effective.melodyRetention, duration: effective.duration,
        inference_steps: effective.inferenceSteps, batch_size: effective.batchSize,
        random_seed: effective.randomSeed, seed: effective.seed || "-1",
        lyrics: effective.instrumental ? "[Instrumental]" : effective.lyrics,
        bpm: effective.bpm, key_scale: effective.keyScale, time_signature: effective.timeSignature,
        output_format: effective.outputFormat, normalize: effective.normalize, target_peak: effective.targetPeak,
        fade_in: effective.fadeIn, fade_out: effective.fadeOut,
        repaint_start: effective.repaintStart, repaint_end: effective.repaintEnd,
        repaint_mode: effective.repaintMode, repaint_strength: effective.repaintStrength,
        source_caption: effective.sourceCaption, flow_min: effective.flowMin,
        flow_max: effective.flowMax, flow_samples: effective.flowSamples,
        no_fsq: effective.noFsq, negative_prompt: effective.negativePrompt,
      });
    }
    try {
      const submitted = await startJob(modeToRun, body);
      setJob(submitted);
      const finished = await waitForJob(submitted.id, setJob);
      const urls = finished.result_urls?.length ? finished.result_urls : finished.result_url ? [finished.result_url] : [];
      setResult((current) => ({ ...current, [modeToRun]: urls }));
      setStatus(await getStatus());
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成失败，请重试");
      return false;
    }
  }

  async function runAgentMusic(plan: MusicPlan) {
    setMode("music");
    setCaption(plan.caption);
    setMusicSettings((current) => ({
      ...current, preserve: plan.preserve,
      melodyRetention: plan.melodyRetention ?? current.melodyRetention,
      duration: plan.duration, editMode: plan.editMode ?? current.editMode,
      quality: plan.quality ?? current.quality,
      inferenceSteps: plan.inferenceSteps ?? current.inferenceSteps,
      batchSize: plan.batchSize ?? current.batchSize,
    }));
    return submit("music", plan);
  }

  const ready = mode === "tts" ? status.tts_ready : status.music_ready;

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="小Y声音工坊首页"><span className="brand-mark"><Cloudy size={28} /></span><span><strong>小Y声音工坊</strong><small>让声音长出新灵感</small></span></a>
        <div className={`engine-status ${ready ? "ready" : working ? "loading" : "idle"}`}><i /> {working ? "正在切换引擎" : `${mode === "tts" ? "配音" : "音乐"}引擎 · ${ready ? "就绪" : "按需启动"}`}</div>
      </header>

      <section className="studio" id="top">
        <div className="mode-tabs" role="tablist" aria-label="创作模式">
          <button className={mode === "tts" ? "active" : ""} onClick={() => { setMode("tts"); setError(""); }}><Mic2 size={18} /> 文字配音</button>
          <button className={mode === "music" ? "active" : ""} onClick={() => { setMode("music"); setError(""); }}><Music2 size={18} /> 音乐改编</button>
        </div>

        <div className="intro-row">
          <div><span className="eyebrow"><Sparkles size={14} /> {mode === "tts" ? "INDEXTTS 2.5" : "ACE-STEP 1.5"}</span><h1>{mode === "tts" ? "把文字，变成喜欢的声音" : "保留熟悉的节奏，添一点新味道"}</h1><p>{mode === "tts" ? "一段清晰参考音，就能开始本地配音。" : "先用预设快速开始，需要时再展开专业选项。"}</p></div>
          <span className={`sprout-mascot ${mode}`}><Leaf size={31} /><i /><b /></span>
        </div>

        {mode === "tts" ? (
          <>
            <section className="form-grid" aria-label="文字配音设置">
              <label className="wide-field"><span className="field-heading"><span>要说的话</span><em>{text.length}/1000</em></span><textarea value={text} maxLength={1000} placeholder="输入想让角色说的内容…" onChange={(event) => setText(event.target.value)} /></label>
              <div className="field-block"><span className="field-heading"><span>音色参考</span><em>必填</em></span><UploadField file={voiceFile} label="上传或拖入参考声音" helper="建议 5–20 秒清晰人声" onChange={setVoiceFile} /></div>
              <div className="controls-stack"><RangeControl label="语速" value={ttsSettings.speed} min={0.65} max={1.6} step={0.05} left="慢一点" right="快一点" display={`${ttsSettings.speed.toFixed(2)}×`} onChange={(speed) => setTtsSettings((current) => ({ ...current, speed }))} /><RangeControl label="情感强度" value={ttsSettings.emotionStrength} min={0.1} max={1} step={0.05} left="自然" right="更有情绪" display={`${Math.round(ttsSettings.emotionStrength * 100)}%`} onChange={(emotionStrength) => setTtsSettings((current) => ({ ...current, emotionStrength }))} /></div>
            </section>
            <TtsAdvancedSettings settings={ttsSettings} emotionReference={emotionReference} onChange={setTtsSettings} onEmotionReference={setEmotionReference} />
          </>
        ) : (
          <>
            <MusicPresetStrip settings={musicSettings} onChange={setMusicSettings} onCaption={setCaption} />
            <section className="form-grid music-form" aria-label="音乐改编设置">
              <div className="field-block"><span className="field-heading"><span>原音乐</span><em>必填</em></span><UploadField file={musicFile} label="上传要改编的音乐" helper="支持 MP3、WAV、FLAC 等" onChange={setMusicFile} /></div>
              <label className="wide-field"><span className="field-heading"><span>想怎么改</span><em>{musicSettings.instrumental ? "纯音乐" : "带人声"}</em></span><textarea value={caption} maxLength={500} onChange={(event) => setCaption(event.target.value)} /><span className="tip-row">描述节奏、情绪、乐器，以及哪些部分必须保持不变</span></label>
              <div className="controls-stack"><RangeControl label="保留原曲" value={musicSettings.preserve} min={0.2} max={1} step={0.01} left="自由改编" right="尽量保持" display={`${Math.round(musicSettings.preserve * 100)}%`} onChange={(preserve) => setMusicSettings((current) => ({ ...current, preserve }))} /><label className="select-field"><span>生成时长</span><select value={musicSettings.duration} onChange={(event) => setMusicSettings((current) => ({ ...current, duration: Number(event.target.value) }))}><option value={-1}>跟随原音乐</option><option value={15}>15 秒</option><option value={30}>30 秒</option><option value={60}>60 秒</option><option value={120}>120 秒</option></select></label></div>
              <div className="vocal-choice"><label><input type="radio" name="vocal-mode" checked={musicSettings.instrumental} onChange={() => setMusicSettings((current) => ({ ...current, instrumental: true }))} /> 纯音乐</label><label><input type="radio" name="vocal-mode" checked={!musicSettings.instrumental} onChange={() => setMusicSettings((current) => ({ ...current, instrumental: false }))} /> 带人声/歌词</label></div>
              {!musicSettings.instrumental && <label className="wide-field lyrics-field"><span className="field-heading"><span>歌词</span><em>支持分段标签</em></span><textarea value={musicSettings.lyrics} placeholder={'[Verse]\n填写歌词…\n[Chorus]\n填写副歌…'} onChange={(event) => setMusicSettings((current) => ({ ...current, lyrics: event.target.value }))} /></label>}
            </section>
            <MusicAdvancedSettings settings={musicSettings} onChange={setMusicSettings} />
          </>
        )}

        <div className="action-row"><PrivacyNote /><button className="primary-button" disabled={working} onClick={() => submit(mode)}>{working ? <LoaderCircle className="spin" size={19} /> : mode === "tts" ? <Mic2 size={19} /> : <Music2 size={19} />}{working ? job?.message : mode === "tts" ? "生成配音" : musicSettings.batchSize > 1 ? `生成 ${musicSettings.batchSize} 个版本` : "生成新音乐"}</button></div>
        {error && <div className="error-message" role="alert">{error}</div>}
        <ResultPanel mode={mode} resultUrls={result[mode]} sourceUrl={sourceUrl} onReset={() => setResult((value) => ({ ...value, [mode]: [] }))} />
      </section>
      <footer>小Y声音工坊 · 所有模型和素材都留在你的电脑里</footer>
      <AgentPet hasMusic={Boolean(musicFile)} working={Boolean(working)} onRunMusic={runAgentMusic} />
    </main>
  );
}

function appendFields(body: FormData, fields: Record<string, string | number | boolean>) {
  Object.entries(fields).forEach(([key, value]) => body.append(key, String(value)));
}
