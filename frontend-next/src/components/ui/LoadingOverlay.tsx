"use client";

// loadingoverlay: pełnoekranowa nakładka „czekaj”.
// używana w krokach air, gdy backend/model wykonuje długą operację.
// renderujemy ją w portalu (document.body), żeby zawsze była nad całą aplikacją.

import React from "react";
import { createPortal } from "react-dom";
import ParticleSpinner from "./ParticleSpinner";
import TypedText from "./TypedText";

interface LoadingOverlayProps {
    isVisible: boolean;
    text?: string;
    message?: string;
}

export default function LoadingOverlay({
    isVisible,
    message = "Proszę czekać, trwa generowanie parametrów",
}: LoadingOverlayProps) {
    if (!isVisible) return null;

    const overlay = (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center h-screen w-screen overflow-hidden">

            {/* tło: półprzezroczyste przyciemnienie + blur */}
            <div className="absolute inset-0 bg-black/70 backdrop-blur-md" />

            {/* panel treści */}
            <div className="relative z-10 flex flex-col items-center justify-center w-full max-w-3xl px-8 space-y-8">

                {/* loader: spinner z cząsteczek */}
                <div className="w-64 h-64">
                    <ParticleSpinner
                        radius={60}
                        particleSize={1.5}
                        count={200}
                        speed={0.03}
                        colors={["#ffffffff", "#ffffffff", "#ffffffff", "#ffffffff", "#ffffff"]}
                    />
                </div>

                {/* komunikat ładowania */}
                <div className="text-center space-y-4">
                    <p className="text-sm font-medium text-purple-200 animate-pulse tracking-wide">
                        {message}
                    </p>

                    {/* animowane kropki (czysto wizualny „puls”) */}
                    <div className="flex items-center justify-center gap-3">
                        <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                        <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                        <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                </div>
            </div>
        </div>
    );

    // używamy portalu, żeby nakładka nie była ograniczona przez layout/overflow rodziców
    return typeof document !== 'undefined' ? createPortal(overlay, document.body) : null;
}
