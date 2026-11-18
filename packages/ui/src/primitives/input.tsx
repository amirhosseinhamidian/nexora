import type { ComponentPropsWithoutRef } from "react";
import { classes, type Size } from "./shared";

export type InputProps = ComponentPropsWithoutRef<"input"> & { inputSize?: Size };

export function Input({ className, inputSize = "md", ...props }: InputProps) {
  return (
    <input className={classes("nx-input", `nx-control--${inputSize}`, className)} {...props} />
  );
}
