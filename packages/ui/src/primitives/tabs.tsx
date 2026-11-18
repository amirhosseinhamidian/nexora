import type { KeyboardEvent, ReactNode } from "react";
import { classes } from "./shared";

export function Tabs({
  children,
  className,
  label,
}: {
  children: ReactNode;
  className?: string;
  label: string;
}) {
  function navigate(event: KeyboardEvent<HTMLDivElement>) {
    if (!(event.target instanceof HTMLButtonElement) || event.target.getAttribute("role") !== "tab")
      return;
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;

    const tabs = Array.from(
      event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]:not(:disabled)'),
    );
    const current = tabs.indexOf(event.target);
    if (current < 0) return;

    const rtl = getComputedStyle(event.currentTarget).direction === "rtl";
    const step = (event.key === "ArrowRight" ? 1 : -1) * (rtl ? -1 : 1);
    let next = (current + step + tabs.length) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;

    event.preventDefault();
    tabs[next].focus();
    tabs[next].click();
  }

  return (
    <div
      aria-label={label}
      className={classes("nx-tabs", className)}
      onKeyDown={navigate}
      role="tablist"
    >
      {children}
    </div>
  );
}
