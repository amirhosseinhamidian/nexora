import type { ReactNode } from "react";
import { classes } from "./shared";

export function StatCard({
  children,
  className,
  icon,
  label,
  value,
  valueClassName,
  valueDirection,
}: {
  children?: ReactNode;
  className?: string;
  icon?: ReactNode;
  label: ReactNode;
  value: ReactNode;
  valueClassName?: string;
  valueDirection?: "ltr" | "rtl" | "auto";
}) {
  return (
    <article className={classes("nx-stat-card", className)}>
      {icon ? (
        <div className="nx-stat-card__heading">
          <span>{label}</span>
          {icon}
        </div>
      ) : (
        <span>{label}</span>
      )}
      <strong className={valueClassName} dir={valueDirection}>
        {value}
      </strong>
      {children}
    </article>
  );
}
