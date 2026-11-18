import { classes } from "./shared";

export function Skeleton({ className, label }: { className?: string; label: string }) {
  return <span aria-label={label} className={classes("nx-skeleton", className)} role="status" />;
}
