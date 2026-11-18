import type { ComponentPropsWithoutRef, ReactNode } from "react";

export function Disclosure({
  children,
  label,
  ...props
}: ComponentPropsWithoutRef<"details"> & { label: ReactNode }) {
  return (
    <details {...props}>
      <summary>{label}</summary>
      {children}
    </details>
  );
}
