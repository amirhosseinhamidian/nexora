import type { ComponentPropsWithRef } from "react";
import { classes, type Size } from "./shared";
import { Spinner } from "./spinner";

export type ButtonProps = ComponentPropsWithRef<"button"> & {
  loading?: boolean;
  size?: Size;
  variant?: "primary" | "secondary" | "ghost" | "danger";
};

export function Button({
  children,
  className,
  disabled,
  loading = false,
  size = "md",
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      aria-busy={loading || undefined}
      className={classes("nx-button", `nx-button--${variant}`, `nx-control--${size}`, className)}
      disabled={disabled || loading}
      type={type}
      {...props}
    >
      {loading ? <Spinner label="" size="sm" /> : null}
      {children}
    </button>
  );
}

export function IconButton({
  className,
  size = "md",
  variant = "ghost",
  ...props
}: ButtonProps & { "aria-label": string }) {
  return (
    <Button
      className={classes("nx-icon-button", className)}
      size={size}
      variant={variant}
      {...props}
    />
  );
}
