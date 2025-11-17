import React from "react";
import "./globals.css";
import { Russo_One, Space_Grotesk } from "next/font/google"; // Dodaj odpowiednią czcionkę
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
