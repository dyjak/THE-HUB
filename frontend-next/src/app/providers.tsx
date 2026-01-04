// providery aplikacji (app router).
// trzymamy to w osobnym pliku, żeby root layout był czytelny,
// a providery dało się łatwo rozbudować (np. o react-query, theme, itp.).
'use client';

import { SessionProvider } from "next-auth/react";

export function Providers({ children }: { children: React.ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}