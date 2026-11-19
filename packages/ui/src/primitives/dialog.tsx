import { type ReactNode, type RefObject, useEffect, useId, useRef } from "react";
import { IconButton } from "./button";
import { classes } from "./shared";

const focusableSelector = [
  "a[href]",
  "button",
  'input:not([type="hidden"])',
  "select",
  "textarea",
  "summary:first-of-type",
  "[tabindex]",
].join(",");

function focusableControls(panel: HTMLElement) {
  return Array.from(panel.querySelectorAll<HTMLElement>(focusableSelector)).filter(
    (element) =>
      element.tabIndex >= 0 &&
      !element.matches(":disabled") &&
      !element.closest('[hidden], [inert], [aria-hidden="true"]') &&
      (element.checkVisibility?.({ visibilityProperty: true }) ?? true),
  );
}

function suspendBackground(overlay: HTMLElement) {
  const inert: HTMLElement[] = [];
  let branch: HTMLElement | null = overlay;
  while (branch?.parentElement) {
    for (const sibling of branch.parentElement.children) {
      if (sibling === branch || !(sibling instanceof HTMLElement) || sibling.hasAttribute("inert"))
        continue;
      sibling.setAttribute("inert", "");
      inert.push(sibling);
    }
    if (branch.parentElement === document.body) break;
    branch = branch.parentElement;
  }
  return () => inert.forEach((element) => element.removeAttribute("inert"));
}

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
    const panel = panelRef.current;
    const overlay = panel?.parentElement;
    if (!open || !panel || !overlay) return;
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const restoreBackground = suspendBackground(overlay);
    (focusableControls(panel)[0] ?? panel).focus();

    const keepFocusInside = (event: FocusEvent) => {
      if (event.target instanceof Node && !panel.contains(event.target)) {
        (focusableControls(panel)[0] ?? panel).focus();
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = focusableControls(panel);
      if (focusable.length === 0) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (document.activeElement === panel) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("focusin", keepFocusInside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("focusin", keepFocusInside);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      restoreBackground();
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
