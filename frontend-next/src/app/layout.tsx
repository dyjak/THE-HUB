import React from "react";
import "./globals.css";
import { Orbitron } from "next/font/google";
import { Pompiere } from "next/font/google";
import { Turret_Road } from "next/font/google";
import { Providers } from "./providers";
import Layout from "@/components/Layout";

const orbitron = Orbitron({ subsets: ["latin"], weight: ["400", "700"] });
const pompiere = Pompiere({ subsets: ["latin"], weight: ["400"] });
const turret_road = Turret_Road({ subsets: ["latin"], weight: ["800"] });

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="pl">
        <body className={`${turret_road.className} bg-black text-white`}>
            <Providers>
                <Layout>{children}</Layout>
            </Providers>
        </body>
        </html>
    );
}