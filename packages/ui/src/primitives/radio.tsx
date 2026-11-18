import type { ComponentPropsWithoutRef } from "react";
import { classes } from "./shared";

export function Radio({ children, className, ...props }: ComponentPropsWithoutRef<"input">) {
  return (
    <label className={classes("nx-choice", className)}>
      <input type="radio" {...props} />
      <span>{children}</span>
    </label>
  );
}
