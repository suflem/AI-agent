import { useEffect, useMemo, useState } from "react";

type LoadingPulseProps = {
  label?: string;
  detail?: string;
  compact?: boolean;
  showBar?: boolean;
};

const DOT_FRAMES = ["", ".", "..", "..."];

function normalizeAction(label: string): string {
  const raw = (label || "").trim();
  if (!raw) return "处理中";
  return raw.replace(/[.]+$/, "").trim() || "处理中";
}

export function LoadingPulse({ label = "思考中", detail = "", compact = false, showBar = true }: LoadingPulseProps) {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setFrame((prev) => (prev + 1) % DOT_FRAMES.length);
    }, 260);
    return () => window.clearInterval(timer);
  }, []);

  const actionText = useMemo(() => {
    const base = normalizeAction(label);
    return `${base}${DOT_FRAMES[frame]}`;
  }, [label, frame]);
  const runClass = frame % 2 === 0 ? "loading-run-bright" : "loading-run-soft";

  return (
    <div className={`loading-wrap ${compact ? "loading-wrap-compact" : ""}`} role="status" aria-live="polite">
      <div className={`loading-pulse ${compact ? "loading-pulse-compact" : ""}`}>
        <span className={`loading-run ${runClass}`} aria-hidden>
          {actionText}
        </span>
        {detail ? <span className="loading-detail">{detail}</span> : null}
      </div>
      {showBar ? (
        <div className="loading-progress-shell" aria-hidden>
          <div className="loading-progress-track">
            <span className={`loading-scan-beam ${runClass}`} />
            <span className="loading-scan-tail" />
          </div>
          <span className={`loading-progress-loop ${runClass}`}>{actionText}</span>
        </div>
      ) : null}
    </div>
  );
}
