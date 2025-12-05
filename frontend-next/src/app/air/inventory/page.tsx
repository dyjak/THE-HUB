"use client";

import React from "react";
import { InventoryBrowser } from "./ui/InventoryBrowser";
import ParticleText from "@/components/ui/ParticleText";

export default function InventoryPage() {
  return (
    <section className="min-h-screen bg-black/0 p-6 md:p-10">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* Header with ParticleText */}
        <div className="bg-gray-900/10 border border-purple-700/30 rounded-2xl shadow-lg shadow-purple-900/10 p-6 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-b from-purple-900/10 to-transparent pointer-events-none" />

          <div className="relative z-10 space-y-4">
            <div className="h-24 md:h-32 w-full">
              <ParticleText
                text="ARCHIWUM"
                colors={["#ffffff"]}
                font="bold 74px system-ui"
                particleSize={2}
                mouseRadius={20}
                mouseStrength={25}
              />
            </div>

            <p className="text-sm text-gray-400 text-center mx-auto">
              Przeglądaj wszystkie dostępne sample audio dla instrumentów. Wybieraj instrumenty i testuj brzmienia do swoich projektów w <span className="text-purple-300/80">aplikacji AIR 4.2.</span> Wszystkie pochodzą z biblioteki <span className="text-pink-300/80">FL Studio 22</span>, a więc to w pełni legalne źródło. Chociaż gdyby było inaczej, to treść tego paragrafu byłaby dokładnie taka jak teraz.
            </p>
          </div>
        </div>

        {/* Inventory Browser */}
        <InventoryBrowser />
      </div>
    </section>
  );
}
