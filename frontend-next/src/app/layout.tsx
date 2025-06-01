import React from "react";
import "./globals.css";
import { Orbitron } from "next/font/google";
import { Providers } from "./providers";
import Layout from "@/components/Layout";

const orbitron = Orbitron({ subsets: ["latin"], weight: ["400", "700"] });

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="pl">
        <body className={`${orbitron.className} bg-black text-white`}>
            <Providers>
                <Layout>{children}</Layout>
            </Providers>
        </body>
        </html>
    );
}