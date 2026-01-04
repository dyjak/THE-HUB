"use client";

// cosmicbutton: przycisk z dwoma canvasami:
// - tło (gwiazdy) jako delikatnie poruszające się punkty,
// - „obwódka” (cząsteczki) krążąca po obrysie zaokrąglonego prostokąta,
//   z lekkim ruchem ambient i reakcją na mysz.
// uwaga: przy `disabled` efekt jest wyłączony (brak inicjalizacji animacji).

import React, { useRef, useEffect, ButtonHTMLAttributes } from "react";

interface CosmicButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    children: React.ReactNode;
    starCount?: number;
    particleCount?: number;
    colors?: string[];
    particleSize?: number;
}

interface Star {
    x: number;
    y: number;
    size: number;
    speed: number;
    opacity: number;
    twinkle: number;
}

interface Particle {
    angle: number;
    distance: number;
    baseDistance: number;
    size: number;
    color: string;
    speed: number;
    offset: number;
}

export default function CosmicButton({
    children,
    starCount = 20,
    particleCount = 30,
    colors = ["#a855f7", "#d946ef", "#f0abfc"],
    particleSize = 1,
    className = "",
    disabled = false,
    ...props
}: CosmicButtonProps) {
    const buttonRef = useRef<HTMLButtonElement>(null);
    const starCanvasRef = useRef<HTMLCanvasElement>(null);
    const particleCanvasRef = useRef<HTMLCanvasElement>(null);
    const starsRef = useRef<Star[]>([]);
    const particlesRef = useRef<Particle[]>([]);
    const mouseRef = useRef({ x: 0, y: 0, active: false });
    const animationRef = useRef<number | null>(null);
    const timeRef = useRef(0);

    useEffect(() => {
        if (disabled) return;

        const starCanvas = starCanvasRef.current;
        const particleCanvas = particleCanvasRef.current;
        const button = buttonRef.current;
        if (!starCanvas || !particleCanvas || !button) return;

        const starCtx = starCanvas.getContext("2d");
        const particleCtx = particleCanvas.getContext("2d");
        if (!starCtx || !particleCtx) return;

        let width = 0;
        let height = 0;

        const init = () => {
            const rect = button.getBoundingClientRect();
            width = rect.width;
            height = rect.height;

            starCanvas.width = width;
            starCanvas.height = height;
            particleCanvas.width = width;
            particleCanvas.height = height;

            // inicjalizacja gwiazd (wolniejszy, subtelny ruch)
            starsRef.current = Array.from({ length: starCount }, () => ({
                x: Math.random() * width,
                y: Math.random() * height,
                size: Math.random() * 1.5 + 0.5,
                speed: Math.random() * 0.25 + 0.05,
                opacity: Math.random() * 0.5 + 0.3,
                twinkle: Math.random() * Math.PI * 2,
            }));

            // inicjalizacja cząsteczek na obwodzie (część zgodnie z ruchem wskazówek, część przeciwnie)
            particlesRef.current = Array.from({ length: particleCount }, (_, i) => ({
                angle: (i / particleCount) * Math.PI * 2,
                distance: 0,
                baseDistance: 8,
                size: Math.random() * 0.1 * particleSize + particleSize,
                color: colors[Math.floor(Math.random() * colors.length)],
                speed: (Math.random() * 0.01 + 0.01) * (Math.random() > 0.5 ? 1 : -1),
                offset: Math.random() * Math.PI * 2,
            }));
        };

        init();

        const animate = () => {
            timeRef.current += 0.02;

            // czyszczenie canvasów (nowa klatka animacji)
            starCtx.clearRect(0, 0, width, height);
            particleCtx.clearRect(0, 0, width, height);

            // rysowanie gwiazd
            starsRef.current.forEach((star) => {
                const twinkle = Math.sin(timeRef.current * 2 + star.twinkle) * 0.3 + 0.7;
                starCtx.fillStyle = `rgba(255, 255, 255, ${star.opacity * twinkle})`;
                starCtx.beginPath();
                starCtx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
                starCtx.fill();

                // delikatny ruch gwiazd (płynięcie w dół, reset po wyjściu poza ekran)
                star.y += star.speed * 0.1;
                if (star.y > height) {
                    star.y = 0;
                    star.x = Math.random() * width;
                }
            });

            // rysowanie cząsteczek na obrysie
            particlesRef.current.forEach((particle) => {
                // wyliczenie pozycji na obrysie zaokrąglonego prostokąta
                particle.angle += particle.speed;

                const radius = 12; // promień zaokrąglenia „obwódki”
                const w2 = width / 2;
                const h2 = height / 2;

                // ruch ambient: lekkie „pływanie” cząsteczek wokół obrysu
                const ambient = Math.sin(timeRef.current + particle.offset) * 3;
                const distance = particle.baseDistance + ambient;

                // mapowanie kąta -> pozycja na zaokrąglonym prostokącie
                const angle = particle.angle;
                const cornerAngle = Math.atan2(h2 - radius, w2 - radius);

                let x, y;

                // określamy, na której krawędzi / w którym narożniku aktualnie jesteśmy
                const normalizedAngle = ((angle % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);

                if (normalizedAngle < cornerAngle) {
                    // prawa krawędź
                    x = w2 + (w2 - radius) + distance;
                    y = h2 + Math.tan(normalizedAngle) * (w2 - radius);
                } else if (normalizedAngle < Math.PI - cornerAngle) {
                    // górna krawędź (od prawego do lewego „narożnika”)
                    const t = (normalizedAngle - cornerAngle) / (Math.PI - 2 * cornerAngle);
                    x = w2 + (w2 - radius) - t * 2 * (w2 - radius);
                    y = h2 - (h2 - radius) - distance;
                } else if (normalizedAngle < Math.PI + cornerAngle) {
                    // lewa krawędź
                    x = w2 - (w2 - radius) - distance;
                    y = h2 - Math.tan(normalizedAngle - Math.PI) * (w2 - radius);
                } else if (normalizedAngle < 2 * Math.PI - cornerAngle) {
                    // dolna krawędź (od lewego do prawego „narożnika”)
                    const t = (normalizedAngle - Math.PI - cornerAngle) / (Math.PI - 2 * cornerAngle);
                    x = w2 - (w2 - radius) + t * 2 * (w2 - radius);
                    y = h2 + (h2 - radius) + distance;
                } else {
                    // domknięcie po prawej stronie (obszar przy dolnym prawym narożniku)
                    x = w2 + (w2 - radius) + distance;
                    y = h2 + Math.tan(normalizedAngle - 2 * Math.PI) * (w2 - radius);
                }

                // interakcja z myszą: odpychanie cząsteczek, gdy kursor jest blisko
                if (mouseRef.current.active) {
                    const dx = mouseRef.current.x - x;
                    const dy = mouseRef.current.y - y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < 60) {
                        const force = (60 - dist) / 60;
                        x -= (dx / dist) * force * 15;
                        y -= (dy / dist) * force * 15;
                    }
                }

                // rysowanie pojedynczej cząsteczki (z poświatą)
                particleCtx.fillStyle = particle.color;
                particleCtx.shadowBlur = 10;
                particleCtx.shadowColor = particle.color;
                particleCtx.beginPath();
                particleCtx.arc(x, y, particle.size, 0, Math.PI * 2);
                particleCtx.fill();
                particleCtx.shadowBlur = 0;
            });

            animationRef.current = requestAnimationFrame(animate);
        };

        animate();

        const handleMouseMove = (e: MouseEvent) => {
            const rect = button.getBoundingClientRect();
            mouseRef.current.x = e.clientX - rect.left;
            mouseRef.current.y = e.clientY - rect.top;
            mouseRef.current.active = true;
        };

        const handleMouseLeave = () => {
            mouseRef.current.active = false;
        };

        button.addEventListener("mousemove", handleMouseMove);
        button.addEventListener("mouseleave", handleMouseLeave);
        window.addEventListener("resize", init);

        return () => {
            if (animationRef.current) cancelAnimationFrame(animationRef.current);
            button.removeEventListener("mousemove", handleMouseMove);
            button.removeEventListener("mouseleave", handleMouseLeave);
            window.removeEventListener("resize", init);
        };
    }, [starCount, particleCount, colors, particleSize, disabled]);

    return (
        <button
            ref={buttonRef}
            className={`relative overflow-hidden ${className} ${disabled ? 'opacity-40 brightness-75 cursor-not-allowed' : ''}`}
            disabled={disabled}
            {...props}
        >
            {/* canvas tła: gwiazdy */}
            <canvas
                ref={starCanvasRef}
                className="absolute inset-0 pointer-events-none"
                style={{ opacity: disabled ? 0 : 1 }}
            />

            {/* treść przycisku nad canvasami */}
            <span className="relative z-10">{children}</span>

            {/* canvas obwódki: cząsteczki krążące po obrysie */}
            <canvas
                ref={particleCanvasRef}
                className="absolute inset-0 pointer-events-none"
                style={{ opacity: disabled ? 0 : 1 }}
            />
        </button>
    );
}
