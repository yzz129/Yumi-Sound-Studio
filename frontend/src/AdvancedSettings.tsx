import { ChevronDown, Gauge, Layers3, SlidersHorizontal, Sparkles } from "lucide-react";
import { RangeControl } from "./components";
import {
  MUSIC_PRESETS,
  QUALITY_STEPS,
  type MusicSettings,
  type TtsSettings,
} from "./settings";

interface TtsAdvancedProps {
  settings: TtsSettings;
  onChange: (settings: TtsSettings) => void;
}

interface MusicAdvancedProps {
  settings: MusicSettings;
  onChange: (settings: MusicSettings) => void;
}

export function TtsAdvancedSettings({ settings, onChange }: TtsAdvancedProps) {
  const patch = (changes: Partial<TtsSettings>) => onChange({ ...settings, ...changes });

  return (
    <details className="advanced-panel">
      <summary><span><SlidersHorizontal size={17} /> 更多配音选择</span><small>指令强度与随机种子</small><ChevronDown size={17} /></summary>
      <div className="advanced-content">
        <section className="setting-section">
          <div className="section-heading"><span><Sparkles size={16} /> 生成偏好</span><small>中文与英文自动识别</small></div>
          <div className="compact-grid three">
            <label className="select-field"><span>随机方式</span><select value={settings.randomSeed ? "random" : "fixed"} onChange={(event) => patch({ randomSeed: event.target.value === "random" })}><option value="random">每次不同</option><option value="fixed">固定种子</option></select></label>
            {!settings.randomSeed && <label className="number-field"><span>种子</span><input type="number" min={0} max={4294967295} step={1} value={settings.seed} onChange={(event) => patch({ seed: event.target.value })} /></label>}
          </div>
          {settings.mode !== "clone" && <div className="mini-range-grid"><RangeControl label="指令跟随强度" value={settings.cfgScale} min={1} max={10} step={0.5} left="自然" right="更遵循描述" display={settings.cfgScale.toFixed(1)} onChange={(cfgScale) => patch({ cfgScale })} /></div>}
          <span className="tip-row">声音克隆跟随参考音频的表达；语速和情绪可在“音色与表演”中用文字描述。</span>
        </section>
      </div>
    </details>
  );
}

export function MusicPresetStrip({ settings, onChange, onCaption }: MusicAdvancedProps & { onCaption: (caption: string) => void }) {
  return (
    <section className="preset-strip" aria-label="音乐风格预设">
      <div className="section-heading"><span><Sparkles size={16} /> 一键风格</span><small>选择后仍可继续修改描述</small></div>
      <div className="preset-row music-presets">
        {MUSIC_PRESETS.map((preset) => (
          <button type="button" key={preset.name} onClick={() => { onCaption(preset.caption); onChange({ ...settings, preserve: preset.preserve, melodyRetention: preset.melodyRetention }); }}>{preset.name}</button>
        ))}
      </div>
    </section>
  );
}

export function MusicAdvancedSettings({ settings, onChange }: MusicAdvancedProps) {
  const patch = (changes: Partial<MusicSettings>) => onChange({ ...settings, ...changes });
  return (
    <details className="advanced-panel">
      <summary><span><SlidersHorizontal size={17} /> 更多音乐选择</span><small>质量、结构、随机性与导出</small><ChevronDown size={17} /></summary>
      <div className="advanced-content">
        <section className="setting-section">
          <div className="section-heading"><span><Layers3 size={16} /> 编辑方式</span><small>越精确的模式，需要越明确的原曲信息</small></div>
          <div className="choice-cards">
            <ChoiceButton active={settings.editMode === "remix"} title="整体改编" copy="保留结构与旋律，改变配器和风格" onClick={() => patch({ editMode: "remix" })} />
            <ChoiceButton active={settings.editMode === "flow_edit"} title="轻量编辑" copy="尽量不动原曲，只改变描述中的元素" onClick={() => patch({ editMode: "flow_edit" })} />
            <ChoiceButton active={settings.editMode === "repaint"} title="局部重绘" copy="只重新生成指定时间范围" onClick={() => patch({ editMode: "repaint" })} />
          </div>
          {settings.editMode === "flow_edit" && (
            <div className="sub-settings">
              <label className="wide-field"><span className="field-heading"><span>原曲描述</span><em>建议填写</em></span><textarea className="compact-textarea" value={settings.sourceCaption} placeholder="例如：急迫的低频鼓点与短促弦乐，没有戏曲乐器" onChange={(event) => patch({ sourceCaption: event.target.value })} /></label>
              <div className="compact-grid three"><RangeControl label="编辑起点" value={settings.flowMin} min={0} max={1} step={0.05} left="开头" right="结尾" display={`${Math.round(settings.flowMin * 100)}%`} onChange={(flowMin) => patch({ flowMin: Math.min(flowMin, settings.flowMax) })} /><RangeControl label="编辑终点" value={settings.flowMax} min={0} max={1} step={0.05} left="开头" right="结尾" display={`${Math.round(settings.flowMax * 100)}%`} onChange={(flowMax) => patch({ flowMax: Math.max(flowMax, settings.flowMin) })} /><RangeControl label="稳定采样" value={settings.flowSamples} min={1} max={4} step={1} left="快速" right="稳定" display={String(settings.flowSamples)} onChange={(flowSamples) => patch({ flowSamples })} /></div>
            </div>
          )}
          {settings.editMode === "repaint" && (
            <div className="sub-settings compact-grid three"><label className="number-field"><span>开始秒数</span><input type="number" min={0} step={0.1} value={settings.repaintStart} onChange={(event) => patch({ repaintStart: Number(event.target.value) })} /></label><label className="number-field"><span>结束秒数</span><input type="number" min={-1} step={0.1} value={settings.repaintEnd} onChange={(event) => patch({ repaintEnd: Number(event.target.value) })} /></label><label className="select-field"><span>重绘方式</span><select value={settings.repaintMode} onChange={(event) => patch({ repaintMode: event.target.value as MusicSettings["repaintMode"] })}><option value="conservative">保守</option><option value="balanced">均衡</option><option value="aggressive">明显</option></select></label><RangeControl label="重绘强度" value={settings.repaintStrength} min={0} max={1} step={0.05} left="轻微" right="明显" display={`${Math.round(settings.repaintStrength * 100)}%`} onChange={(repaintStrength) => patch({ repaintStrength })} /></div>
          )}
        </section>

        <section className="setting-section">
          <div className="section-heading"><span><Gauge size={16} /> 生成质量</span><small>当前 Turbo 模型，8 步为官方均衡值</small></div>
          <div className="compact-grid four">
            <label className="select-field"><span>质量档位</span><select value={settings.quality} onChange={(event) => { const quality = event.target.value as MusicSettings["quality"]; patch({ quality, inferenceSteps: QUALITY_STEPS[quality] }); }}><option value="fast">快速预览</option><option value="balanced">均衡推荐</option><option value="high">高质量</option></select></label>
            <label className="select-field"><span>生成版本</span><select value={settings.batchSize} onChange={(event) => patch({ batchSize: Number(event.target.value) })}><option value={1}>1 个版本</option><option value={2}>2 个版本</option><option value={3}>3 个版本</option><option value={4}>4 个版本</option></select></label>
            <label className="select-field"><span>输出格式</span><select value={settings.outputFormat} onChange={(event) => patch({ outputFormat: event.target.value as MusicSettings["outputFormat"] })}><option value="wav">WAV 无损</option><option value="flac">FLAC 无损</option><option value="mp3">MP3 轻量</option></select></label>
            <label className="select-field"><span>随机方式</span><select value={settings.randomSeed ? "random" : "fixed"} onChange={(event) => patch({ randomSeed: event.target.value === "random" })}><option value="random">每次不同</option><option value="fixed">固定种子</option></select></label>
          </div>
          {!settings.randomSeed && <label className="number-field seed-field"><span>种子</span><input value={settings.seed} inputMode="numeric" onChange={(event) => patch({ seed: event.target.value.replace(/[^0-9-]/g, "") })} /></label>}
          <div className="mini-range-grid">
            <RangeControl label="推理步数" value={settings.inferenceSteps} min={4} max={20} step={1} left="更快" right="更细致" display={String(settings.inferenceSteps)} onChange={(inferenceSteps) => patch({ inferenceSteps, quality: inferenceSteps <= 6 ? "fast" : inferenceSteps <= 10 ? "balanced" : "high" })} />
            <RangeControl label="旋律保留" value={settings.melodyRetention} min={0} max={0.5} step={0.01} left="风格优先" right="旋律优先" display={`${Math.round(settings.melodyRetention * 100)}%`} onChange={(melodyRetention) => patch({ melodyRetention })} />
          </div>
        </section>

        <section className="setting-section">
          <div className="section-heading"><span><SlidersHorizontal size={16} /> 音乐结构与后期</span><small>留空即可自动识别原音乐</small></div>
          <div className="compact-grid four">
            <label className="number-field"><span>BPM</span><input type="number" min={30} max={300} placeholder="自动" value={settings.bpm} onChange={(event) => patch({ bpm: event.target.value })} /></label>
            <label className="select-field"><span>调式</span><select value={settings.keyScale} onChange={(event) => patch({ keyScale: event.target.value })}><option value="">自动</option>{["C major","C minor","D major","D minor","E major","E minor","F major","F minor","G major","G minor","A major","A minor","B major","B minor"].map((key) => <option key={key}>{key}</option>)}</select></label>
            <label className="select-field"><span>拍号</span><select value={settings.timeSignature} onChange={(event) => patch({ timeSignature: event.target.value })}><option value="">自动</option><option value="2">2/4</option><option value="3">3/4</option><option value="4">4/4</option><option value="6">6/8</option></select></label>
            <label className="select-field"><span>标准化</span><select value={settings.normalize ? "on" : "off"} onChange={(event) => patch({ normalize: event.target.value === "on" })}><option value="on">自动标准化</option><option value="off">保留原动态</option></select></label>
          </div>
          <div className="mini-range-grid">
            <RangeControl label="淡入" value={settings.fadeIn} min={0} max={10} step={0.5} left="无" right="10 秒" display={`${settings.fadeIn.toFixed(1)}s`} onChange={(fadeIn) => patch({ fadeIn })} />
            <RangeControl label="淡出" value={settings.fadeOut} min={0} max={10} step={0.5} left="无" right="10 秒" display={`${settings.fadeOut.toFixed(1)}s`} onChange={(fadeOut) => patch({ fadeOut })} />
          </div>
          <label className="wide-field"><span className="field-heading"><span>避免出现</span><em>负面提示</em></span><textarea className="compact-textarea" value={settings.negativePrompt} placeholder="例如：欢快、电子音色、密集配器、人声" onChange={(event) => patch({ negativePrompt: event.target.value })} /></label>
        </section>
      </div>
    </details>
  );
}

function ChoiceButton({ active, title, copy, onClick }: { active: boolean; title: string; copy: string; onClick: () => void }) {
  return <button type="button" className={active ? "active" : ""} onClick={onClick}><strong>{title}</strong><small>{copy}</small></button>;
}
