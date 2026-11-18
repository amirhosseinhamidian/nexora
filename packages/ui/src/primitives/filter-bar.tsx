import type { ReactNode } from "react";

export function FilterBar({ children, label }: { children: ReactNode; label: string }) {
  return (
    <section aria-label={label} className="nx-filter-bar">
      {children}
    </section>
  );
}
