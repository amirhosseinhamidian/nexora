import type { CSSProperties } from "react";

export function Progress({ label, value }: { label: string; value?: number }) {
  const boundedValue = value === undefined ? undefined : Math.min(100, Math.max(0, value));
  return (
    <div className="nx-progress">
      <div className="nx-progress__label">
        <span>{label}</span>
        {boundedValue === undefined ? null : <span>{boundedValue}%</span>}
      </div>
      <div
        aria-label={label}
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={boundedValue}
        className="nx-progress__track"
        role="progressbar"
      >
        <span
          className={boundedValue === undefined ? "indeterminate" : undefined}
          style={{ "--nx-progress-size": `${boundedValue ?? 35}%` } as CSSProperties}
        />
      </div>
    </div>
  );
}
