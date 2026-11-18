import type { ReactNode } from "react";
import { classes, type Tone } from "./shared";

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
