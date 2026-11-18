import type { ComponentPropsWithoutRef } from "react";
import { classes } from "./shared";

export function Switch({ children, className, ...props }: ComponentPropsWithoutRef<"input">) {
  return (
    <label className={classes("nx-switch", className)}>
      <input role="switch" type="checkbox" {...props} />
      <span aria-hidden="true" className="nx-switch__track">
        <span />
      </span>
      <span>{children}</span>
    </label>
  );
}
