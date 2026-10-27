import "@fontsource-variable/inter";
import "@nexora/ui/tokens.css";
import "../globals.css";

import type { Metadata } from "next";
import localFont from "next/font/local";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { ThemeProvider } from "@/components/theme-provider";
import { directionFor, isLocale, locales } from "@/i18n/config";

const vazirmatn = localFont({
  display: "swap",
  src: "../../assets/fonts/vazirmatn/Vazirmatn-Variable.ttf",
  variable: "--font-vazirmatn",
  weight: "100 900",
});

export const metadata: Metadata = {
  description: "Private portfolio intelligence and financial decision workspace",
  title: "Nexora",
};

export const dynamic = "force-dynamic";

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: Readonly<{
  children: ReactNode;
  params: Promise<{ locale: string }>;
}>) {
  const { locale } = await params;
  if (!isLocale(locale)) {
    notFound();
  }
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <html
      className={vazirmatn.variable}
      dir={directionFor(locale)}
      lang={locale}
      suppressHydrationWarning
    >
      <body className={locale === "fa" ? "font-fa" : "font-en"}>
        <ThemeProvider nonce={nonce}>{children}</ThemeProvider>
      </body>
    </html>
  );
}
