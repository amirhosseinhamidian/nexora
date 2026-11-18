import type { ComponentPropsWithoutRef } from "react";
import { classes } from "./shared";

export function FieldError({ className, ...props }: ComponentPropsWithoutRef<"p">) {
  return <p className={classes("nx-field__error", className)} role="alert" {...props} />;
}
