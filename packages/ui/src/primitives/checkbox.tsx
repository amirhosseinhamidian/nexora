import type { ComponentPropsWithoutRef } from "react";
import { classes } from "./shared";

export function Checkbox({ children, className, ...props }: ComponentPropsWithoutRef<"input">) {
  return (
    <label className={classes("nx-choice", className)}>
      <input type="checkbox" {...props} />
      <span>{children}</span>
    </label>
  );
}
