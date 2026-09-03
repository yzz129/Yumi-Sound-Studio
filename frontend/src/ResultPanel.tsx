import { Download, RotateCcw, Sparkles } from "lucide-react";
import type { Mode } from "./types";
import Waveform from "./Waveform";

interface ResultPanelProps {
  mode: Mode;
  resultUrls: string[];
  sourceUrl: string | null;
  onReset: () => void;
}

export default function ResultPanel({ mode, resultUrls, sourceUrl, onReset }: ResultPanelProps) {
  if (resultUrls.length === 0) {
    return (
      <section className="result-empty">
        <span><Sparkles size={19} /></span>
        <p>生成后，作品会安静地出现在这里</p>
      </section>
    );
  }

  return (
    <section className="result-panel" aria-live="polite">
      <div className="result-title">
        <div><span className="result-dot" /> <strong>生成完成</strong><small> 可以试听和下载了</small></div>
        <button type="button" className="text-button" onClick={onReset}><RotateCcw size={15} /> 继续修改</button>
      </div>
      <Waveform />
      <div className={`players ${mode === "music" ? "dual" : ""}`}>
        {mode === "music" && sourceUrl && (
          <label><span>原音乐</span><audio controls src={sourceUrl} /></label>
        )}
        {resultUrls.map((resultUrl, index) => (
          <label className="result-variant" key={resultUrl}>
            <span>{mode === "tts" ? "新配音" : resultUrls.length > 1 ? `新音乐 ${index + 1}` : "新音乐"}</span>
            <audio controls src={resultUrl} />
            <a className="download-button compact" href={resultUrl} download><Download size={15} /> 下载{resultUrls.length > 1 ? `版本 ${index + 1}` : "音频"}</a>
          </label>
        ))}
      </div>
    </section>
  );
}
