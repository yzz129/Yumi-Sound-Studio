export default function Waveform() {
  const bars = [12, 20, 32, 24, 48, 36, 22, 42, 58, 38, 28, 46, 66, 52, 34, 44, 24, 40, 62, 48, 28, 18, 36, 54, 40, 24, 32, 58, 46, 20, 28, 44, 64, 40, 26, 34, 50, 30, 18, 28, 44, 34];
  return (
    <div className="waveform" aria-hidden="true">
      {bars.map((height, index) => <i key={index} style={{ height }} />)}
    </div>
  );
}

