import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { classes } from "./shared";

export function Disclosure({
  children,
  className,
  label,
  ...props
}: ComponentPropsWithoutRef<"details"> & { label: ReactNode }) {
  return (
    <details {...props} className={classes("nx-disclosure", className)}>
      <summary>{label}</summary>
      {children}
    </details>
  );
}
