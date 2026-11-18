import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { AuthenticatedShell } from "@/components/authenticated-shell";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

export default async function WorkspaceLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return (
    <AuthenticatedShell dictionary={getDictionary(locale)} locale={locale}>
      {children}
    </AuthenticatedShell>
  );
}
