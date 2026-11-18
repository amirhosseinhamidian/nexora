import type { ReactNode } from "react";
import { classes, type Tone } from "./shared";

type StatePanelProps = {
  action?: ReactNode;
  children?: ReactNode;
  className?: string;
  headingLevel?: 2 | 3;
  icon?: ReactNode;
  title: ReactNode;
  tone?: Tone;
  variant: "empty" | "error" | "offline" | "degraded";
};

function StatePanel({
  action,
  children,
  className,
  headingLevel = 3,
  icon,
  title,
  tone,
  variant,
}: StatePanelProps) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const resolvedTone =
    tone ?? (variant === "error" ? "danger" : variant === "degraded" ? "warning" : "neutral");
  return (
    <section
      className={classes(
        "nx-state-panel",
        `nx-state-panel--${variant}`,
        `nx-tone--${resolvedTone}`,
        className,
      )}
      role={variant === "error" ? "alert" : undefined}
    >
      {icon}
      <div className="nx-state-panel__content">
        <Heading>{title}</Heading>
        {children ? <div>{children}</div> : null}
      </div>
      {action}
    </section>
  );
}

export function EmptyState(props: Omit<StatePanelProps, "variant">) {
  return <StatePanel variant="empty" {...props} />;
}

export function ErrorState(props: Omit<StatePanelProps, "variant">) {
  return <StatePanel variant="error" {...props} />;
}

export function OfflineState(props: Omit<StatePanelProps, "variant">) {
  return <StatePanel variant="offline" {...props} />;
}

export function DegradedState(props: Omit<StatePanelProps, "variant">) {
  return <StatePanel variant="degraded" {...props} />;
}
