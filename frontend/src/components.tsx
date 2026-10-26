import { Check, FileAudio, Upload, X } from "lucide-react";
import { useRef } from "react";

interface UploadFieldProps {
  file: File | null;
  label: string;
  helper: string;
  accept?: string;
  onChange: (file: File | null) => void;
}

export function UploadField({ file, label, helper, accept = "audio/*,.wav,.mp3,.flac,.m4a,.ogg,.aac", onChange }: UploadFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      className={`upload-field ${file ? "has-file" : ""}`}
      role="button"
      tabIndex={0}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(event) => event.key === "Enter" && inputRef.current?.click()}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        onChange(event.dataTransfer.files[0] || null);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={(event) => onChange(event.target.files?.[0] || null)}
      />
      <span className="upload-icon">{file ? <FileAudio size={22} /> : <Upload size={22} />}</span>
      <span className="upload-copy">
        <strong>{file ? file.name : label}</strong>
        <small>{file ? `${formatSize(file.size)} · 点击更换` : helper}</small>
      </span>
      {file && (
        <button
          type="button"
          className="clear-file"
          aria-label="移除音频"
          onClick={(event) => {
            event.stopPropagation();
            onChange(null);
          }}
        >
          <X size={17} />
        </button>
      )}
    </div>
  );
}

interface RangeControlProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  left: string;
  right: string;
  display: string;
  onChange: (value: number) => void;
}

export function RangeControl(props: RangeControlProps) {
  const percent = ((props.value - props.min) / (props.max - props.min)) * 100;
  return (
    <label className="range-control">
      <span className="field-heading">
        <span>{props.label}</span>
        <em>{props.display}</em>
      </span>
      <input
        type="range"
        min={props.min}
        max={props.max}
        step={props.step}
        value={props.value}
        style={{ "--range-fill": `${percent}%` } as React.CSSProperties}
        onChange={(event) => props.onChange(Number(event.target.value))}
      />
      <span className="range-ends"><small>{props.left}</small><small>{props.right}</small></span>
    </label>
  );
}

export function PrivacyNote() {
  return <span className="privacy"><Check size={14} /> 本地处理，保护你的素材</span>;
}

function formatSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

