"use client";

import { LiquidGlass } from "@liquidglass/react";
import { ReactNode } from "react";

interface FluidGlassBackgroundProps {
    children: ReactNode;
    className?: string;
}

export const FluidGlassBackground = ({ children, className = "" }: FluidGlassBackgroundProps) => {
    return (
        <div className={`relative overflow-hidden rounded-xl ${className}`}>
            <div className="absolute inset-0 -z-10">
                <LiquidGlass displacementScale={1} />
            </div>
            <div className="relative z-10 p-6">
                {children}
            </div>
        </div>
    );
};
