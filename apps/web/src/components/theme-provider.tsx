"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { PropsWithChildren } from "react";

export function ThemeProvider({ children, nonce }: PropsWithChildren<{ nonce?: string }>) {
  return (
    <NextThemesProvider
      attribute="data-theme"
      defaultTheme="system"
      disableTransitionOnChange
      enableSystem
      nonce={nonce}
      storageKey="nexora-theme"
    >
      {children}
    </NextThemesProvider>
  );
}
