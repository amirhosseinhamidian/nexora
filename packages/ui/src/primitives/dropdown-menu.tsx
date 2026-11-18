import type { ReactNode } from "react";

export function DropdownMenu({
  children,
  label,
  open,
}: {
  children: ReactNode;
  label: string;
  open: boolean;
}) {
  return open ? (
    <div aria-label={label} className="nx-dropdown" role="menu">
      {children}
    </div>
  ) : null;
}
