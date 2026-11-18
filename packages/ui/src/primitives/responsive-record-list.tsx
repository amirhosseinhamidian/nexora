import type { ReactNode } from "react";
import { classes } from "./shared";

export function ResponsiveRecordList({
  as: List = "ul",
  children,
  className,
  label,
}: {
  as?: "ul" | "ol";
  children: ReactNode;
  className?: string;
  label: string;
}) {
  return (
    <List aria-label={label} className={classes("nx-record-list", className)} role="list">
      {children}
    </List>
  );
}
