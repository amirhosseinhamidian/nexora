import { type ReactNode, type RefObject, useEffect, useId, useRef } from "react";
import { IconButton } from "./button";
import { classes } from "./shared";

const focusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function useOverlay(
  open: boolean,
  onClose: () => void,
  panelRef: RefObject<HTMLDivElement | null>,
) {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.querySelector<HTMLElement>(focusableSelector)?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(focusableSelector),
      );
      if (focusable.length === 0) {
        event.preventDefault();
        panelRef.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [open, panelRef]);
}

export type OverlayProps = {
  children: ReactNode;
  className?: string;
  closeLabel: string;
  description?: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  open: boolean;
  title: ReactNode;
  variant?: "modal" | "drawer" | "sheet";
};

function Overlay({
  children,
  className,
  closeLabel,
  description,
  footer,
  onClose,
  open,
  title,
  variant = "modal",
}: OverlayProps) {
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  useOverlay(open, onClose, panelRef);
  if (!open) return null;
  return (
    <div
      className={classes("nx-overlay", `nx-overlay--${variant}`)}
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div
        aria-describedby={description ? descriptionId : undefined}
        aria-labelledby={titleId}
        aria-modal="true"
        className={classes("nx-overlay__panel", className)}
        ref={panelRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="nx-overlay__header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description ? <p id={descriptionId}>{description}</p> : null}
          </div>
          <IconButton aria-label={closeLabel} onClick={onClose}>
            <span aria-hidden="true">×</span>
          </IconButton>
        </header>
        <div className="nx-overlay__body">{children}</div>
        {footer ? <footer className="nx-overlay__footer">{footer}</footer> : null}
      </div>
    </div>
  );
}

export function Modal(props: OverlayProps) {
  return <Overlay variant="modal" {...props} />;
}

export function Drawer(props: OverlayProps) {
  return <Overlay variant="drawer" {...props} />;
}

export function Sheet(props: OverlayProps) {
  return <Overlay variant="sheet" {...props} />;
}
