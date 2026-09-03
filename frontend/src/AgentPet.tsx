import { Check, LoaderCircle, Music2, Send, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import mascot from "./assets/illustrations/empty-mascot.webp";
import mascotCelebrate from "./assets/illustrations/agent-celebrate.png";
import mascotFocused from "./assets/illustrations/agent-focused.png";
import mascotSleepy from "./assets/illustrations/agent-sleepy.png";
import mascotThinking from "./assets/illustrations/agent-thinking.png";
import type { MusicEditMode, MusicQuality } from "./settings";

export interface MusicPlan {
  caption: string;
  preserve: number;
  duration: number;
  melodyRetention?: number;
  editMode?: MusicEditMode;
  quality?: MusicQuality;
  inferenceSteps?: number;
  batchSize?: number;
}

interface AgentPetProps {
  hasMusic: boolean;
  working: boolean;
  onRunMusic: (plan: MusicPlan) => Promise<boolean>;
}

interface Message {
  role: "user" | "agent";
  text: string;
  plan?: MusicPlan;
}

const QUICK_PROMPTS = [
  "保持原节奏，原声小一点，多加快板和二胡，直接生成",
  "做成低沉紧张的纯音乐，尽量保持原曲",
  "减少乐器，只突出锣鼓和快板，生成 30 秒",
];

const PET_POSITION_KEY = "xiaoy-audio-agent-pet-position:v1";

interface PetPosition {
  x: number;
  y: number;
}

interface PetDrag {
  pointerId: number;
  startX: number;
  startY: number;
  originX: number;
  originY: number;
  lastX: number;
  lastY: number;
  moved: boolean;
}

type PetPose = "idle" | "sleepy" | "focused" | "thinking" | "celebrate";

const PET_IMAGES: Record<PetPose, string> = {
  idle: mascot,
  sleepy: mascotSleepy,
  focused: mascotFocused,
  thinking: mascotThinking,
  celebrate: mascotCelebrate,
};

const POSE_LABELS: Record<PetPose, string> = {
  idle: "小Y在等你",
  sleepy: "小Y打了个盹",
  focused: "小Y认真听着",
  thinking: "小Y正在思考",
  celebrate: "小Y完成啦",
};

function launcherSize() {
  return window.innerWidth <= 720 ? 70 : 88;
}

function clampPetPosition(position: PetPosition): PetPosition {
  const size = launcherSize();
  const margin = 8;
  return {
    x: Math.max(margin, Math.min(window.innerWidth - size - margin, position.x)),
    y: Math.max(margin, Math.min(window.innerHeight - size - margin, position.y)),
  };
}

function defaultPetPosition(): PetPosition {
  const size = launcherSize();
  return clampPetPosition({ x: window.innerWidth - size - 22, y: window.innerHeight - size - 20 });
}

function readPetPosition(): PetPosition {
  try {
    const saved = JSON.parse(localStorage.getItem(PET_POSITION_KEY) || "null");
    if (Number.isFinite(saved?.x) && Number.isFinite(saved?.y)) return clampPetPosition(saved);
  } catch {
    // Ignore stale local data and return to the safe default position.
  }
  return defaultPetPosition();
}

export default function AgentPet({ hasMusic, working, onRunMusic }: AgentPetProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [celebrating, setCelebrating] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [idlePose, setIdlePose] = useState<"idle" | "sleepy">("idle");
  const [messages, setMessages] = useState<Message[]>([]);
  const [petPosition, setPetPosition] = useState(readPetPosition);
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef<PetDrag | null>(null);

  useEffect(() => {
    const keepPetVisible = () => {
      setPetPosition((current) => {
        const next = clampPetPosition(current);
        localStorage.setItem(PET_POSITION_KEY, JSON.stringify(next));
        return next;
      });
    };
    window.addEventListener("resize", keepPetVisible, { passive: true });
    return () => window.removeEventListener("resize", keepPetVisible);
  }, []);

  useEffect(() => {
    const saveTimer = window.setTimeout(() => {
      localStorage.setItem(PET_POSITION_KEY, JSON.stringify(petPosition));
    }, 120);
    return () => window.clearTimeout(saveTimer);
  }, [petPosition]);

  useEffect(() => {
    const moveFromWindow = (event: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== event.pointerId) return;
      event.preventDefault();
      const dx = event.clientX - drag.startX;
      const dy = event.clientY - drag.startY;
      if (Math.hypot(dx, dy) > 5) drag.moved = true;
      const next = clampPetPosition({ x: drag.originX + dx, y: drag.originY + dy });
      drag.lastX = next.x;
      drag.lastY = next.y;
      setPetPosition(next);
    };

    const finishFromWindow = (event: PointerEvent, cancelled: boolean) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== event.pointerId) return;
      const next = cancelled
        ? clampPetPosition({ x: drag.lastX, y: drag.lastY })
        : clampPetPosition({
          x: drag.originX + event.clientX - drag.startX,
          y: drag.originY + event.clientY - drag.startY,
        });
      dragRef.current = null;
      setPetPosition(next);
      localStorage.setItem(PET_POSITION_KEY, JSON.stringify(next));
      setDragging(false);
      if (!cancelled && !drag.moved) setOpen(true);
    };

    const finish = (event: PointerEvent) => finishFromWindow(event, false);
    const cancel = (event: PointerEvent) => finishFromWindow(event, true);
    window.addEventListener("pointermove", moveFromWindow, { capture: true, passive: false });
    window.addEventListener("pointerup", finish, { capture: true });
    window.addEventListener("pointercancel", cancel, { capture: true });
    return () => {
      window.removeEventListener("pointermove", moveFromWindow, true);
      window.removeEventListener("pointerup", finish, true);
      window.removeEventListener("pointercancel", cancel, true);
    };
  }, []);

  useEffect(() => {
    if (open || busy || working || celebrating || dragging || hovered) {
      setIdlePose("idle");
      return;
    }
    const poseTimer = window.setInterval(() => {
      setIdlePose((current) => current === "idle" ? "sleepy" : "idle");
    }, 7000);
    return () => window.clearInterval(poseTimer);
  }, [open, busy, working, celebrating, dragging, hovered]);

  function startPetDrag(event: ReactPointerEvent<HTMLButtonElement>) {
    if (event.button !== 0) return;
    event.preventDefault();
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // Pointer capture is an enhancement; the last valid pointer position still keeps dragging safe.
    }
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: petPosition.x,
      originY: petPosition.y,
      lastX: petPosition.x,
      lastY: petPosition.y,
      moved: false,
    };
    setDragging(true);
  }

  function keepLastPetPosition(event: ReactPointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const next = clampPetPosition({ x: drag.lastX, y: drag.lastY });
    dragRef.current = null;
    setPetPosition(next);
    localStorage.setItem(PET_POSITION_KEY, JSON.stringify(next));
    setDragging(false);
  }

  async function send(value = input) {
    const request = value.trim();
    if (!request || busy || working) return;
    const plan = createMusicPlan(request);
    setInput("");
    setMessages((current) => [...current, { role: "user", text: request }]);
    if (!hasMusic) {
      setMessages((current) => [...current, { role: "agent", text: "我已经听懂改编方向啦。先在音乐改编页上传原音乐，我就能自动开工。", plan }]);
      return;
    }

    setBusy(true);
    setMessages((current) => [...current, {
      role: "agent",
      text: "参数已经整理好，我现在切换音乐引擎并开始生成。",
      plan,
    }]);
    const completed = await onRunMusic(plan);
    setBusy(false);
    if (completed) {
      setCelebrating(true);
      setMessages((current) => [...current, { role: "agent", text: "完成啦！新音乐已经放到页面下方，可以和原音乐对比试听。" }]);
      window.setTimeout(() => setCelebrating(false), 3600);
    } else {
      setMessages((current) => [...current, { role: "agent", text: "这次没有顺利完成，可以看看页面上的错误提示，再让我重试。" }]);
    }
  }

  const petPose: PetPose = celebrating
    ? "celebrate"
    : busy || working
      ? "thinking"
      : open || dragging || hovered
        ? "focused"
        : idlePose;
  const petImage = PET_IMAGES[petPose];

  return (
    <>
      {open && <button className="agent-backdrop" aria-label="关闭小Y" onClick={() => setOpen(false)} />}
      <aside className={`agent-drawer ${open ? "is-open" : ""}`} aria-hidden={!open}>
        <header className="agent-header">
          <span className="agent-avatar"><img src={petImage} alt="小Y云朵宠物" /></span>
          <div><strong>小Y声音 Agent</strong><small><i className={busy || working ? "busy" : ""} /> {busy || working ? "正在制作" : "本地待命"}</small></div>
          <button aria-label="关闭" onClick={() => setOpen(false)}><X size={17} /></button>
        </header>
        <div className="agent-scroll">
          {messages.length === 0 ? (
            <section className="agent-welcome">
              <div className="agent-welcome-art"><img src={mascot} alt="小Y抱着四叶草" /><Sparkles /></div>
              <p className="agent-eyebrow">自动配乐助手</p>
              <h2>告诉我想怎么改，<br />剩下的交给小Y</h2>
              <p>我会理解节奏、情绪、乐器和保留程度，自动填写参数并调用本地音乐模型。</p>
              <div className="agent-quick-list">
                {QUICK_PROMPTS.map((prompt) => (
                  <button key={prompt} onClick={() => send(prompt)}><span><Music2 /></span>{prompt}</button>
                ))}
              </div>
            </section>
          ) : (
            <div className="agent-messages">
              {messages.map((message, index) => (
                <div className={`agent-message ${message.role}`} key={`${message.role}-${index}`}>
                  <span>{message.text}</span>
                  {message.plan && (
                    <article className="agent-plan">
                      <div><Music2 /><strong>自动配乐方案</strong></div>
                      <p>{message.plan.caption}</p>
                      <span><Check /> 保留原曲 {Math.round(message.plan.preserve * 100)}%</span>
                      <span><Check /> {message.plan.duration < 0 ? "跟随原音乐时长" : `${message.plan.duration} 秒`}</span>
                      <span><Check /> {message.plan.editMode === "flow_edit" ? "轻量编辑" : message.plan.editMode === "repaint" ? "局部重绘" : "整体改编"}</span>
                      <span><Check /> {message.plan.quality === "high" ? "高质量" : message.plan.quality === "fast" ? "快速预览" : "均衡质量"}</span>
                    </article>
                  )}
                </div>
              ))}
              {(busy || working) && <div className="agent-thinking"><LoaderCircle /> 正在调用 ACE-Step 生成音乐…</div>}
            </div>
          )}
        </div>
        <div className="agent-composer">
          <textarea value={input} placeholder="例如：原声小一点，多加快板和二胡…" onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} />
          <button disabled={!input.trim() || busy || working} onClick={() => send()} aria-label="发送"><Send /></button>
          <small>小Y只操作当前页面和本地模型，不会上传你的音乐</small>
        </div>
      </aside>

      <button
        className={`agent-launcher pose-${petPose} ${dragging ? "dragging" : ""}`}
        style={{ left: petPosition.x, top: petPosition.y }}
        onPointerDown={startPetDrag}
        onLostPointerCapture={keepLastPetPosition}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onDragStart={(event) => event.preventDefault()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setOpen(true);
            return;
          }
          const step = event.shiftKey ? 48 : 16;
          const delta = event.key === "ArrowLeft" ? { x: -step, y: 0 }
            : event.key === "ArrowRight" ? { x: step, y: 0 }
              : event.key === "ArrowUp" ? { x: 0, y: -step }
                : event.key === "ArrowDown" ? { x: 0, y: step }
                  : null;
          if (!delta) return;
          event.preventDefault();
          setPetPosition((current) => {
            const next = clampPetPosition({ x: current.x + delta.x, y: current.y + delta.y });
            localStorage.setItem(PET_POSITION_KEY, JSON.stringify(next));
            return next;
          });
        }}
        aria-label={`${POSE_LABELS[petPose]}。点击打开，按住拖动`}
        title="按住拖动位置，点击打开助手"
      >
        <img key={petPose} src={petImage} alt={POSE_LABELS[petPose]} draggable={false} />
        <em>AI</em><i>✦</i><b>·</b><small>拖动我</small>
      </button>
    </>
  );
}

function createMusicPlan(request: string): MusicPlan {
  const compact = request.replace(/\s+/g, "").slice(0, 320);
  let preserve = 0.82;
  if (/基本一致|尽量保持|不要改变|保留原曲|原节奏/.test(compact)) preserve = 0.94;
  if (/自由改编|变化大|重新创作/.test(compact)) preserve = 0.48;
  if (/稍微改|少量加入|不要太多/.test(compact)) preserve = Math.max(preserve, 0.9);
  const durationMatch = compact.match(/(15|30|45|60|90|120)秒/);
  const duration = durationMatch ? Number(durationMatch[1]) : -1;
  const countMatch = compact.match(/([2-4])个(?:版本|方案)/);
  const batchSize = countMatch ? Number(countMatch[1]) : 1;
  const editMode: MusicEditMode = /局部|只改.{0,5}(?:秒|段)|重绘/.test(compact)
    ? "repaint"
    : /基本不变|只增加|只添加|轻微修改|轻量编辑/.test(compact)
      ? "flow_edit"
      : "remix";
  const quality: MusicQuality = /高质量|精细|最好/.test(compact) ? "high" : /快速|预览/.test(compact) ? "fast" : "balanced";
  const inferenceSteps = quality === "high" ? 14 : quality === "fast" ? 6 : 8;
  let melodyRetention = 0.2;
  if (/基本一致|旋律不变|保持旋律|原旋律/.test(compact)) melodyRetention = 0.25;
  if (/自由改编|旋律变化/.test(compact)) melodyRetention = 0.08;

  const requirements = ["纯音乐", request.replace(/直接生成|自动生成|帮我生成|开始生成|生成配乐/g, "").trim()];
  if (/原声小|降低原声|压低原声/.test(compact)) requirements.push("降低原音在混音中的音量与存在感");
  if (/快板/.test(compact)) requirements.push("突出清晰有力的快板节拍");
  if (/二胡/.test(compact)) requirements.push("二胡只承担克制的情绪线条");
  if (/锣鼓/.test(compact)) requirements.push("锣鼓点到为止，不要喧闹");
  if (/紧张|急迫|低沉|压迫/.test(compact)) requirements.push("整体低沉、紧张、急迫，避免欢快");
  requirements.push("保持原有速度、节奏骨架和主要旋律走向，减少多余元素，无人声");

  return { caption: [...new Set(requirements.filter(Boolean))].join("；"), preserve, melodyRetention, duration, editMode, quality, inferenceSteps, batchSize };
}
