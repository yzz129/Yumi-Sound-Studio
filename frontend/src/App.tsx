import { Cloudy, Leaf, LoaderCircle, Mic2, Music2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { MusicAdvancedSettings, MusicPresetStrip, TtsAdvancedSettings } from "./AdvancedSettings";
import { getStatus, startJob, waitForJob } from "./api";
import AgentPet, { type MusicPlan } from "./AgentPet";
import { PrivacyNote, RangeControl, UploadField } from "./components";
import ResultPanel from "./ResultPanel";
import { DEFAULT_MUSIC_SETTINGS, DEFAULT_TTS_SETTINGS, VOICE_PRESETS, type MusicSettings, type TtsSettings } from "./settings";
import type { EngineStatus, JobState, Mode } from "./types";

const initialStatus: EngineStatus = { active: null, tts_ready: false, music_ready: false, busy: false };

export default function App() {
  const [mode, setMode] = useState<Mode>("tts");
  const [status, setStatus] = useState(initialStatus);
  const [voiceFile, setVoiceFile] = useState<File | null>(null);
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
      if (!text.trim()) {
        setError("先输入要说的话吧。");
        return false;
      }
      if (ttsSettings.mode !== "design" && (!voiceFile || !ttsSettings.refText.trim())) {
        setError("请上传参考声音，并填写这段音频的准确文字稿。");
        return false;
      }
      if (ttsSettings.mode !== "clone" && !ttsSettings.instruction.trim()) {
        setError("请描述想要的音色、情绪或说话方式。");
        return false;
      }
      if (!ttsSettings.randomSeed && (!/^\d+$/.test(ttsSettings.seed) || Number(ttsSettings.seed) > 4294967295)) {
        setError("固定种子需要是 0 到 4294967295 之间的整数。");
        return false;
      }
      if (ttsSettings.mode !== "design" && voiceFile) body.append("reference", voiceFile);
      body.append("text", text.trim());
      appendFields(body, {
        mode: ttsSettings.mode,
        ref_text: ttsSettings.mode === "design" ? "" : ttsSettings.refText.trim(),
        instruction: ttsSettings.mode === "clone" ? "" : ttsSettings.instruction.trim(),
        cfg_scale: ttsSettings.mode === "clone" ? 1 : ttsSettings.cfgScale,
        seed: ttsSettings.randomSeed ? -1 : ttsSettings.seed,
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
          <div><span className="eyebrow"><Sparkles size={14} /> {mode === "tts" ? "BREEZE TTS 2" : "ACE-STEP 1.5"}</span><h1>{mode === "tts" ? "把文字，变成喜欢的声音" : "保留熟悉的节奏，添一点新味道"}</h1><p>{mode === "tts" ? "克隆熟悉的音色，或用文字设计一个新声音。" : "先用预设快速开始，需要时再展开专业选项。"}</p></div>
          <span className={`sprout-mascot ${mode}`}><Leaf size={31} /><i /><b /></span>
        </div>

        {mode === "tts" ? (
          <>
            <section className="preset-strip" aria-label="配音方式">
              <div className="section-heading"><span><Mic2 size={16} /> 配音方式</span><small>支持中文与英文</small></div>
              <div className="choice-cards">
                {([{ value: "clone", title: "声音克隆", copy: "跟随参考音色与原有表达" }, { value: "design", title: "文字设计音色", copy: "描述声音，无需参考音频" }, { value: "direction", title: "音色与表演", copy: "保留音色，用文字指导表达" }] as const).map((item) => <button type="button" key={item.value} aria-pressed={ttsSettings.mode === item.value} className={ttsSettings.mode === item.value ? "active" : ""} onClick={() => { setTtsSettings((current) => ({ ...current, mode: item.value })); setError(""); }}><strong>{item.title}</strong><small>{item.copy}</small></button>)}
              </div>
            </section>
            <section className="form-grid tts-form" aria-label="文字配音设置">
              <label className="wide-field tts-text"><span className="field-heading"><span>要说的话</span><em>{text.length}/1000</em></span><textarea value={text} maxLength={1000} placeholder="输入想让角色说的内容，可加入 [笑]、[叹气] 等表演标记…" onChange={(event) => { setText(event.target.value); setError(""); }} /></label>
              {ttsSettings.mode !== "design" && <>
                <div className="field-block"><span className="field-heading"><span>音色参考</span><em>必填</em></span><UploadField file={voiceFile} label="上传或拖入参考声音" helper="WAV / MP3 / FLAC / OGG，清晰完整人声" accept=".wav,.mp3,.flac,.ogg" onChange={(file) => { setVoiceFile(file); setError(""); }} /></div>
                <label className="wide-field"><span className="field-heading"><span>参考音频文字稿</span><em>必填</em></span><textarea value={ttsSettings.refText} placeholder="逐字填写参考音频中的全部内容，包含重复说的话…" onChange={(event) => { setTtsSettings((current) => ({ ...current, refText: event.target.value })); setError(""); }} /></label>
              </>}
              {ttsSettings.mode !== "clone" && <label className="wide-field tts-instruction"><span className="field-heading"><span>{ttsSettings.mode === "design" ? "想要的声音" : "表演指令"}</span><em>必填</em></span><textarea className="compact-textarea" value={ttsSettings.instruction} placeholder={ttsSettings.mode === "design" ? "例如：温暖、清澈的年轻女声，用舒缓自然的语气讲故事。英文配音请用英文描述。" : "例如：语速稍慢，用克制、严肃的语气说话，句尾适当停顿。"} onChange={(event) => { setTtsSettings((current) => ({ ...current, instruction: event.target.value })); setError(""); }} /><span className="tip-row">描述音色、语速与情绪；指令语言尽量与配音文字一致。</span></label>}
            </section>
            {ttsSettings.mode !== "clone" && <div className="preset-row voice-presets">{VOICE_PRESETS.map((preset) => <button type="button" key={preset.name} onClick={() => { setTtsSettings((current) => ({ ...current, instruction: preset.instruction })); setError(""); }}>{preset.name}</button>)}</div>}
            <TtsAdvancedSettings settings={ttsSettings} onChange={setTtsSettings} />
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
