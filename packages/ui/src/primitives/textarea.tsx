import type { ComponentPropsWithoutRef } from "react";
import { classes } from "./shared";

export function Textarea({ className, ...props }: ComponentPropsWithoutRef<"textarea">) {
  return <textarea className={classes("nx-input", "nx-textarea", className)} {...props} />;
}
