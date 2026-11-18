import type { CSSProperties, ReactNode } from "react";

export function ChartLegend({
  items,
  label,
}: {
  items: Array<{ color: string; id: string; label: ReactNode }>;
  label: string;
}) {
  return (
    <ul aria-label={label} className="nx-chart-legend">
      {items.map((item) => (
        <li key={item.id}>
          <span aria-hidden="true" style={{ "--nx-legend-color": item.color } as CSSProperties} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
