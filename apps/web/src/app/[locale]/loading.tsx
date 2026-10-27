import { LoaderCircle } from "lucide-react";

export default function Loading() {
  return (
    <main className="centered-state">
      <section aria-live="polite" className="state-card">
        <span className="state-icon loading">
          <LoaderCircle aria-hidden="true" className="spin" size={24} />
        </span>
        <h1>NEXORA</h1>
      </section>
    </main>
  );
}
