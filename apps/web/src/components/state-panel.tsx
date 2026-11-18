import { Button, Spinner } from "@nexora/ui/primitives";
import { AlertTriangle, WifiOff } from "lucide-react";
import Link from "next/link";

type StatePanelProps = {
  action?: { href?: string; label: string; onClick?: () => void };
  description: string;
  kind: "error" | "loading" | "offline" | "session";
  title: string;
};

export function StatePanel({ action, description, kind, title }: StatePanelProps) {
  const Icon = kind === "offline" ? WifiOff : AlertTriangle;
  return (
    <main className="centered-state" id="main-content">
      <section aria-live="polite" className="state-card">
        <span className={`state-icon ${kind}`}>
          {kind === "loading" ? (
            <Spinner label="" size="lg" />
          ) : (
            <Icon aria-hidden="true" size={24} />
          )}
        </span>
        <h1>{title}</h1>
        <p>{description}</p>
        {action?.href ? (
          <Link className="primary-button" href={action.href}>
            {action.label}
          </Link>
        ) : action?.onClick ? (
          <Button className="primary-button" onClick={action.onClick} type="button">
            {action.label}
          </Button>
        ) : null}
      </section>
    </main>
  );
}
