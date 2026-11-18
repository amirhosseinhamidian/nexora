"use client";

import {
  type ButtonHTMLAttributes,
  type ComponentPropsWithoutRef,
  type HTMLAttributes,
  type ReactNode,
  type RefObject,
  useEffect,
  useId,
  useRef,
} from "react";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";
type Size = "sm" | "md" | "lg";

function classes(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
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
      <span>{children}</span>
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

export type FieldProps = {
  children: ReactNode;
  className?: string;
  description?: ReactNode;
  error?: ReactNode;
  id: string;
  label: ReactNode;
  optionalLabel?: ReactNode;
};

export function FormField({
  children,
  className,
  description,
  error,
  id,
  label,
  optionalLabel,
}: FieldProps) {
  return (
    <div className={classes("nx-field", className)} data-invalid={Boolean(error) || undefined}>
      <div className="nx-field__label-row">
        <label htmlFor={id}>{label}</label>
        {optionalLabel ? <span>{optionalLabel}</span> : null}
      </div>
      {description ? (
        <p className="nx-field__description" id={`${id}-description`}>
          {description}
        </p>
      ) : null}
      {children}
      {error ? <FieldError id={`${id}-error`}>{error}</FieldError> : null}
    </div>
  );
}

export function FieldError({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <p className="nx-field__error" id={id} role="alert">
      {children}
    </p>
  );
}

type InputProps = ComponentPropsWithoutRef<"input"> & { inputSize?: Size };

export function Input({ className, inputSize = "md", ...props }: InputProps) {
  return (
    <input className={classes("nx-input", `nx-control--${inputSize}`, className)} {...props} />
  );
}

export function SearchInput({ className, type = "search", ...props }: InputProps) {
  return <Input className={classes("nx-search-input", className)} type={type} {...props} />;
}

export function Textarea({ className, ...props }: ComponentPropsWithoutRef<"textarea">) {
  return <textarea className={classes("nx-input", "nx-textarea", className)} {...props} />;
}

export function Select({ className, ...props }: ComponentPropsWithoutRef<"select">) {
  return <select className={classes("nx-input", "nx-select", className)} {...props} />;
}

export function Checkbox({ children, className, ...props }: ComponentPropsWithoutRef<"input">) {
  return (
    <label className={classes("nx-choice", className)}>
      <input type="checkbox" {...props} />
      <span>{children}</span>
    </label>
  );
}

export function Radio({ children, className, ...props }: ComponentPropsWithoutRef<"input">) {
  return (
    <label className={classes("nx-choice", className)}>
      <input type="radio" {...props} />
      <span>{children}</span>
    </label>
  );
}

export function Switch({ children, className, ...props }: ComponentPropsWithoutRef<"input">) {
  return (
    <label className={classes("nx-switch", className)}>
      <input role="switch" type="checkbox" {...props} />
      <span aria-hidden="true" className="nx-switch__track">
        <span />
      </span>
      <span>{children}</span>
    </label>
  );
}

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
      <div>
        {title ? <strong>{title}</strong> : null}
        <div>{children}</div>
      </div>
    </div>
  );
}

export type ToastMessage = {
  action?: ReactNode;
  description?: ReactNode;
  id: string;
  title: ReactNode;
  tone?: Tone;
};

export function ToastRegion({ label, messages }: { label: string; messages: ToastMessage[] }) {
  return (
    <section aria-label={label} aria-live="polite" className="nx-toast-region">
      {messages.map((message) => (
        <article
          className={classes("nx-toast", `nx-tone--${message.tone ?? "neutral"}`)}
          key={message.id}
          role={message.tone === "danger" ? "alert" : "status"}
        >
          <div>
            <strong>{message.title}</strong>
            {message.description ? <p>{message.description}</p> : null}
          </div>
          {message.action}
        </article>
      ))}
    </section>
  );
}

export function Progress({ label, value }: { label: string; value?: number }) {
  const boundedValue = value === undefined ? undefined : Math.min(100, Math.max(0, value));
  return (
    <div className="nx-progress">
      <div className="nx-progress__label">
        <span>{label}</span>
        {boundedValue === undefined ? null : <span>{boundedValue}%</span>}
      </div>
      <div
        aria-label={label}
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={boundedValue}
        className="nx-progress__track"
        role="progressbar"
      >
        <span
          className={boundedValue === undefined ? "indeterminate" : undefined}
          style={{ inlineSize: `${boundedValue ?? 35}%` }}
        />
      </div>
    </div>
  );
}

export function Spinner({ label, size = "md" }: { label: string; size?: Size }) {
  return (
    <span
      aria-label={label || undefined}
      className={classes("nx-spinner", `nx-spinner--${size}`)}
      role={label ? "status" : undefined}
    >
      <span aria-hidden="true" />
    </span>
  );
}

export function Skeleton({ className, label }: { className?: string; label: string }) {
  return <span aria-label={label} className={classes("nx-skeleton", className)} role="status" />;
}

type StatePanelProps = {
  action?: ReactNode;
  children?: ReactNode;
  className?: string;
  title: ReactNode;
  tone?: Tone;
  variant: "empty" | "error" | "offline" | "degraded";
};

function StatePanel({ action, children, className, title, tone, variant }: StatePanelProps) {
  const resolvedTone =
    tone ?? (variant === "error" ? "danger" : variant === "degraded" ? "warning" : "neutral");
  return (
    <section
      className={classes(
        "nx-state-panel",
        `nx-state-panel--${variant}`,
        `nx-tone--${resolvedTone}`,
        className,
      )}
      role={variant === "error" ? "alert" : undefined}
    >
      <div>
        <h3>{title}</h3>
        {children ? <div>{children}</div> : null}
      </div>
      {action}
    </section>
  );
}

export function EmptyState(props: Omit<StatePanelProps, "variant">) {
  return <StatePanel variant="empty" {...props} />;
}

export function ErrorState(props: Omit<StatePanelProps, "variant">) {
  return <StatePanel variant="error" {...props} />;
}

export function OfflineState(props: Omit<StatePanelProps, "variant">) {
  return <StatePanel variant="offline" {...props} />;
}

export function DegradedState(props: Omit<StatePanelProps, "variant">) {
  return <StatePanel variant="degraded" {...props} />;
}

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

type OverlayProps = {
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

export function ConfirmationDialog({
  cancelLabel,
  confirmLabel,
  destructive = false,
  onCancel,
  onConfirm,
  ...props
}: Omit<OverlayProps, "children" | "closeLabel" | "footer" | "onClose" | "variant"> & {
  cancelLabel: string;
  confirmLabel: string;
  destructive?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Modal
      closeLabel={cancelLabel}
      footer={
        <>
          <Button onClick={onCancel} variant="secondary">
            {cancelLabel}
          </Button>
          <Button onClick={onConfirm} variant={destructive ? "danger" : "primary"}>
            {confirmLabel}
          </Button>
        </>
      }
      onClose={onCancel}
      {...props}
    >
      {null}
    </Modal>
  );
}

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

export function Popover({
  children,
  className,
  open,
}: {
  children: ReactNode;
  className?: string;
  open: boolean;
}) {
  return open ? <div className={classes("nx-popover", className)}>{children}</div> : null;
}

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

export function Table({ className, ...props }: ComponentPropsWithoutRef<"table">) {
  return (
    <div className="nx-table-scroll" tabIndex={0}>
      <table className={classes("nx-table", className)} {...props} />
    </div>
  );
}

export function ResponsiveRecordList({
  children,
  className,
  label,
}: {
  children: ReactNode;
  className?: string;
  label: string;
}) {
  return (
    <ul aria-label={label} className={classes("nx-record-list", className)}>
      {children}
    </ul>
  );
}

export function Pagination({
  currentPage,
  label,
  nextLabel,
  onPageChange,
  previousLabel,
  totalPages,
}: {
  currentPage: number;
  label: string;
  nextLabel: string;
  onPageChange: (page: number) => void;
  previousLabel: string;
  totalPages: number;
}) {
  return (
    <nav aria-label={label} className="nx-pagination">
      <Button
        disabled={currentPage <= 1}
        onClick={() => onPageChange(currentPage - 1)}
        variant="secondary"
      >
        {previousLabel}
      </Button>
      <span aria-current="page">
        {currentPage} / {totalPages}
      </span>
      <Button
        disabled={currentPage >= totalPages}
        onClick={() => onPageChange(currentPage + 1)}
        variant="secondary"
      >
        {nextLabel}
      </Button>
    </nav>
  );
}

export function Tabs({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div aria-label={label} className="nx-tabs" role="tablist">
      {children}
    </div>
  );
}

export function FilterBar({ children, label }: { children: ReactNode; label: string }) {
  return (
    <section aria-label={label} className="nx-filter-bar">
      {children}
    </section>
  );
}

export function StatCard({
  children,
  label,
  value,
}: {
  children?: ReactNode;
  label: ReactNode;
  value: ReactNode;
}) {
  return (
    <article className="nx-stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {children}
    </article>
  );
}

export function ChartContainer({
  children,
  description,
  table,
  title,
}: {
  children: ReactNode;
  description: ReactNode;
  table: ReactNode;
  title: ReactNode;
}) {
  const descriptionId = useId();
  return (
    <section aria-describedby={descriptionId} className="nx-chart" role="figure">
      <header>
        <h3>{title}</h3>
        <p id={descriptionId}>{description}</p>
      </header>
      <div aria-hidden="true" className="nx-chart__visual">
        {children}
      </div>
      <div className="nx-chart__table">{table}</div>
    </section>
  );
}

export function ChartLegend({
  items,
  label,
}: {
  items: Array<{ color: string; id: string; label: ReactNode }>;
  label: string;
}) {
  return (
    <ul aria-label={label} className="nx-chart-legend">
      {items.map((item) => (
        <li key={item.id}>
          <span aria-hidden="true" style={{ backgroundColor: item.color }} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

export function ComparisonBlock({
  after,
  afterLabel,
  before,
  beforeLabel,
  title,
}: {
  after: ReactNode;
  afterLabel: ReactNode;
  before: ReactNode;
  beforeLabel: ReactNode;
  title: ReactNode;
}) {
  return (
    <section className="nx-comparison">
      <h3>{title}</h3>
      <dl>
        <div>
          <dt>{beforeLabel}</dt>
          <dd>{before}</dd>
        </div>
        <div>
          <dt>{afterLabel}</dt>
          <dd>{after}</dd>
        </div>
      </dl>
    </section>
  );
}
