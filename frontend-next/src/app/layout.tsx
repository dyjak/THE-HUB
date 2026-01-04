// główny layout aplikacji next.js (app router).
// w tym miejscu spinamy:
// - globalne style (globals.css),
// - fonty z next/font,
// - providery (np. next-auth),
// - „shell” strony (komponent layout z nawigacją/stopką).

import React from "react";
import "./globals.css";
import { Russo_One, Space_Grotesk } from "next/font/google"; // fonty z google fonts (konfiguracja w runtime next)
import { Providers } from "./providers";
import Layout from "@/components/Layout";

const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], weight: ["400", "700"] });

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="pl">
        <body className={`${spaceGrotesk.className} bg-black text-white`}>            <Providers>
                <Layout>{children}</Layout>
            </Providers>
        </body>
        </html>
    );
}
