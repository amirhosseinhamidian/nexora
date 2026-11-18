import type { ReactNode } from "react";
import { classes } from "./shared";

export function Popover({
  children,
  className,
  open,
}: {
  children: ReactNode;
  className?: string;
  open: boolean;
}) {
  return open ? <div className={classes("nx-popover", className)}>{children}</div> : null;
}
