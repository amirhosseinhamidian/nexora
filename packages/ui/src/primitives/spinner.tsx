import { classes, type Size } from "./shared";

export function Spinner({ label, size = "md" }: { label: string; size?: Size }) {
  return (
    <span
      aria-label={label || undefined}
      className={classes("nx-spinner", `nx-spinner--${size}`)}
      role={label ? "status" : undefined}
    >
      <span aria-hidden="true" />
    </span>
  );
}
