import { notFound } from "next/navigation";

import { AuthPanel } from "@/components/auth-panel";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

export default async function LoginPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <AuthPanel dictionary={getDictionary(locale)} locale={locale} mode="login" />;
}
