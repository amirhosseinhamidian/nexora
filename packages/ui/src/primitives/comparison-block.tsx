import type { ReactNode } from "react";

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
