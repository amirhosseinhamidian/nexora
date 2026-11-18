import { type ReactNode, useId } from "react";
import { classes } from "./shared";

export function ChartContainer({
  children,
  className,
  description,
  icon,
  table,
  tableClassName,
  title,
}: {
  children: ReactNode;
  className?: string;
  description: ReactNode;
  icon?: ReactNode;
  table: ReactNode;
  tableClassName?: string;
  title: ReactNode;
}) {
  const id = useId();
  return (
    <section
      aria-describedby={`${id}-description`}
      aria-labelledby={`${id}-title`}
      className={classes("nx-chart", className)}
      role="figure"
    >
      <header className="nx-chart__heading">
        <div>
          <h3 id={`${id}-title`}>{title}</h3>
          <p id={`${id}-description`}>{description}</p>
        </div>
        {icon}
      </header>
      {table ? (
        <>
          <div aria-hidden="true" className="nx-chart__visual">
            {children}
          </div>
          <div className={classes("nx-chart__table", tableClassName)}>{table}</div>
        </>
      ) : (
        children
      )}
    </section>
  );
}
