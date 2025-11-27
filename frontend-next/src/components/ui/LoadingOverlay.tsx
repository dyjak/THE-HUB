"use client";

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

            {/* Backdrop with blur */}
            <div className="absolute inset-0 bg-black/70 backdrop-blur-md" />

            {/* Content panel */}
            <div className="relative z-10 flex flex-col items-center justify-center w-full max-w-3xl px-8 space-y-8">

                {/* Particle Spinner */}
                <div className="w-64 h-64">
                    <ParticleSpinner
                        radius={60}
                        particleSize={1.5}
                        count={200}
                        speed={0.03}
                        colors={["#ffffffff", "#ffffffff", "#ffffffff", "#ffffffff", "#ffffff"]}
                    />
                </div>

                {/* Loading message */}
                <div className="text-center space-y-4">
                    <p className="text-sm font-medium text-purple-200 animate-pulse tracking-wide">
                        {message}
                    </p>

                    {/* Animated dots */}
                    <div className="flex items-center justify-center gap-3">
                        <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                        <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                        <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                </div>
            </div>
        </div>
    );

    // Use portal to render outside the current DOM hierarchy
    return typeof document !== 'undefined' ? createPortal(overlay, document.body) : null;
}
