import {
  Activity,
  Bell,
  BookOpen,
  Boxes,
  BriefcaseBusiness,
  CheckCircle2,
  Download,
  FileChartColumn,
  LayoutDashboard,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { notFound } from "next/navigation";

import { FoundationControls } from "@/components/foundation-controls";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

const navigationIcons = [
  LayoutDashboard,
  BriefcaseBusiness,
  FileChartColumn,
  Bell,
  BookOpen,
  Download,
  Settings,
] as const;

export default async function FoundationPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) {
    notFound();
  }

  const dictionary = getDictionary(locale);
  const navigation = Object.values(dictionary.navigation);
  const cards = [
    {
      detail: dictionary.page.cards.webDetail,
      icon: Boxes,
      title: dictionary.page.cards.webTitle,
      value: dictionary.page.cards.webValue,
    },
    {
      detail: dictionary.page.cards.apiDetail,
      icon: Activity,
      title: dictionary.page.cards.apiTitle,
      value: dictionary.page.cards.apiValue,
    },
    {
      detail: dictionary.page.cards.designDetail,
      icon: ShieldCheck,
      title: dictionary.page.cards.designTitle,
      value: dictionary.page.cards.designValue,
    },
  ];

  return (
    <div className="application-shell">
      <a className="skip-link" href="#main-content">
        {dictionary.skipToContent}
      </a>
      <aside className="sidebar">
        <div className="brand" dir="ltr">
          <span aria-hidden="true" className="brand-mark">
            N
          </span>
          <span>{dictionary.brand}</span>
        </div>
        <nav aria-label={dictionary.navigation.overview}>
          <ul className="navigation-list">
            {navigation.map((label, index) => {
              const Icon = navigationIcons[index];
              return (
                <li key={label}>
                  <a
                    className={index === 0 ? "navigation-link active" : "navigation-link"}
                    href="#"
                  >
                    <Icon aria-hidden="true" size={19} />
                    <span>{label}</span>
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="environment-pill">
            <span className="status-dot" />
            {dictionary.header.environment}
          </div>
          <div className="topbar-actions">
            <span className="mode-pill">{dictionary.header.mode}</span>
            <FoundationControls dictionary={dictionary.header} locale={locale} />
          </div>
        </header>

        <main id="main-content" className="main-content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">{dictionary.page.eyebrow}</p>
              <h1>{dictionary.page.title}</h1>
              <p>{dictionary.page.description}</p>
            </div>
            <div className="ready-badge">
              <CheckCircle2 aria-hidden="true" size={18} />
              <span>{dictionary.page.ready}</span>
            </div>
          </div>

          <section aria-label={dictionary.page.status} className="metric-grid">
            {cards.map(({ detail, icon: Icon, title, value }) => (
              <article className="metric-card" key={title}>
                <div className="metric-card-heading">
                  <span>{title}</span>
                  <Icon aria-hidden="true" size={20} />
                </div>
                <strong dir="ltr">{value}</strong>
                <p>{detail}</p>
              </article>
            ))}
          </section>

          <section className="boundary-card">
            <div className="boundary-heading">
              <div>
                <p className="eyebrow">{dictionary.page.status}</p>
                <h2>{dictionary.page.boundaryTitle}</h2>
              </div>
              <ShieldCheck aria-hidden="true" size={28} />
            </div>
            <ul className="boundary-list">
              {Object.values(dictionary.page.boundaries).map((boundary) => (
                <li key={boundary}>
                  <CheckCircle2 aria-hidden="true" size={18} />
                  <span>{boundary}</span>
                </li>
              ))}
            </ul>
            <p className="next-stage">{dictionary.page.next}</p>
          </section>
        </main>
      </div>
    </div>
  );
}
