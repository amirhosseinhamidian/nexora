import type { HTMLAttributes, ReactNode } from "react";
import { classes, type Tone } from "./shared";

export function Alert({
  children,
  className,
  title,
  tone = "neutral",
  ...props
}: Omit<HTMLAttributes<HTMLDivElement>, "title"> & { title?: ReactNode; tone?: Tone }) {
  return (
    <div
      className={classes("nx-alert", `nx-tone--${tone}`, className)}
      role={tone === "danger" ? "alert" : "status"}
      {...props}
    >
      {title ? (
        <div>
          <strong>{title}</strong>
          <div>{children}</div>
        </div>
      ) : (
        children
      )}
    </div>
  );
}
