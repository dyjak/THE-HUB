"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

export default function StarBackground() {
    const [stars, setStars] = useState<{
        id: number;
        x: string;
        y: string;
        delay: number;
        size: string;
        opacity: number;
    }[]>([]);


    useEffect(() => {
        const generatedStars = Array.from({ length: 15 }, (_, i) => {
            const size = Math.random() * (3 - 0.1) + 0.1;  // Zakres 0.1px - 3px
            const speed = 2.5 - ((size - 0.1) / (3 - 0.1)) * (2.5 - 0.5); // Im mniejsza gwiazda, tym wolniejsza
            return {
                id: i,
                x: Math.random() * 100 + "vw",
                y: Math.random() * 100 + "vh",
                delay: Math.random() * 5,
                size: (Math.random() * (3 - 0.5) + 0.5) + "px",  // Zakres: 0.1px - 3px
                opacity: Math.random() * 0.7 + 0.1,               // Jasność 0.2 - 0.9
                speed: speed,
            };
            //random = (Math.random() * (max - min) + min)
        });
        setStars(generatedStars);
    }, []);

    //zmiana randomów co jakiś czas
    // useEffect(() => {
    //     const interval = setInterval(() => {
    //         setStars((prevStars) =>
    //             prevStars.map((star) => ({
    //                 ...star,
    //                 x: Math.random() * 100 + "vw",  // Losowe X
    //                 y: Math.random() * 100 + "vh",  // Losowe Y
    //             }))
    //         );
    //     }, 1000); // Zmiana co sekundę
    //
    //     return () => clearInterval(interval); // Czyszczenie interwału
    // }, []);

    return (
        <div className="fixed top-0 left-0 w-full h-full z-[-1] overflow-hidden pointer-events-none">
            {stars.map((star) => (
                <motion.div
                    key={star.id}
                    className="absolute rounded-full"
                    style={{
                        left: star.x,
                        top: star.y,
                        width: star.size,
                        height: star.size,
                        opacity: star.opacity,
                        backgroundColor: "pink",
                        boxShadow: `0px 0px 6px 2px rgba(255,255,255,0.6), 0px 0px 20px 6px rgba(173,216,230,0.3)`,
                        filter: "drop-shadow(0px 10px 10px rgba(173,216,230,0.3))",
                        transform: "scaleY(7)",
                    }}
                    animate={{
                        y: ["0vh", "100vh"],                                    // Spadanie gwiazdy na dół ekranu
                        scaleY: [1, Math.random() * 70 + 12],                   // Dodatkowe rozszerzenie podczas spadania
                        scaleX: [1, 0.01],                                  // Dodatkowe zwężenie podczas spadania
                        opacity: [star.opacity, 0],                             // Zanikanie
                    }}
                    transition={{
                        //duration: star.speed,                                   // Prędkość spadania zależna od wielkości gwiazdy
                        repeat: Infinity,
                        ease: "linear",
                    }}
                />
            ))}
        </div>
    );
}
