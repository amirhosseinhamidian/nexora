import { type ReactNode, useId } from "react";

export function Tooltip({ children, content }: { children: ReactNode; content: ReactNode }) {
  const id = useId();
  return (
    <span className="nx-tooltip">
      <span aria-describedby={id} className="nx-tooltip__trigger" tabIndex={0}>
        {children}
      </span>
      <span className="nx-tooltip__content" id={id} role="tooltip">
        {content}
      </span>
    </span>
  );
}
