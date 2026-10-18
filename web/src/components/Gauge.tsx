/**
 * Semicircle gauge: forest-green progress with a knob, the remainder drawn as
 * amber and coral segments (the reference design's "financial health" dial).
 */
export function Gauge({ value, label, caption }: { value: number; label: string; caption: string }) {
  const v = Math.max(0, Math.min(1, value));
  const r = 80;
  const cx = 100;
  const cy = 96;
  const gap = 0.025; // fraction of the arc left blank between segments
  const point = (t: number) => {
    const a = Math.PI * (1 - t);
    return [cx + r * Math.cos(a), cy - r * Math.sin(a)] as const;
  };
  const arc = (from: number, to: number) => {
    if (to - from <= 0.001) return "";
    const [x1, y1] = point(from);
    const [x2, y2] = point(to);
    return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
  };
  const rest = 1 - v;
  const amberEnd = v + rest * 0.55;
  const [kx, ky] = point(v);

  return (
    <div className="gauge">
      <svg viewBox="0 0 200 112" role="img" aria-label={`${label}: ${Math.round(v * 100)}%`}>
        <path d={arc(0, 1)} className="g-track" />
        <path d={arc(0, Math.max(0, v - gap / 2))} className="g-fill" />
        <path d={arc(Math.min(1, v + gap), Math.max(v + gap, amberEnd - gap / 2))} className="g-amber" />
        <path d={arc(Math.min(1, amberEnd + gap / 2), 1)} className="g-coral" />
        <circle cx={kx} cy={ky} r="9" className="g-knob" />
      </svg>
      <div className="gauge-read">
        <span className="gauge-value">{Math.round(v * 100)}%</span>
        <span className="gauge-caption">{caption}</span>
      </div>
    </div>
  );
}
