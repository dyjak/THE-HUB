"use client";

// particlespinner: loader na canvasie w formie „wiru” cząsteczek.
// ideowo to układ w współrzędnych biegunowych (kąt + promień), z lekkim ruchem ambient
// i opcjonalnym wpływem myszy (odpychanie / zaburzenie trajektorii).

import React, { useRef, useEffect } from "react";

interface ParticleSpinnerProps {
    className?: string;
    colors?: string[];
    particleSize?: number;
    mouseRadius?: number;
    mouseStrength?: number;
    radius?: number;
    count?: number;
    speed?: number;
}

interface Particle {
    x: number;
    y: number;
    // współrzędne biegunowe dla pozycji bazowej (kąt + promień)
    angle: number;
    dist: number;

    size: number;
    color: string;

    // fazy ruchu ambient (żeby cząsteczki nie poruszały się identycznie)
    phaseX: number;
    phaseY: number;
}

export default function ParticleSpinner({
    className = "",
    colors = ["#d946ef", "#a855f7", "#c026d3", "#e879f9", "#ffffff"],
    particleSize = 2,
    mouseRadius = 50,
    mouseStrength = 5,
    radius = 10,
    count = 150,
    speed = 0.02,
}: ParticleSpinnerProps) {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const particlesRef = useRef<Particle[]>([]);
    const mouseRef = useRef({ x: 0, y: 0, active: false });
    const animationRef = useRef<number | null>(null);
    const timeRef = useRef(0);
    const rotationRef = useRef(0);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        let width = canvas.width;
        let height = canvas.height;

        const init = () => {
            // dopasowanie canvasa do rodzica
            const parent = canvas.parentElement;
            if (parent) {
                canvas.width = parent.clientWidth;
                canvas.height = parent.clientHeight;
            }
            width = canvas.width;
            height = canvas.height;

            const particles: Particle[] = [];

            for (let i = 0; i < count; i++) {
                // rozkład równomierny po okręgu
                const baseAngle = (i / count) * Math.PI * 2;
                // losowa wariancja promienia dla efektu „grubej” obręczy
                const dist = radius + (Math.random() - 0.5) * 20;

                const color = colors[Math.floor(Math.random() * colors.length)];

                particles.push({
                    x: width / 2, // start w centrum (potem „odjeżdża” na orbitę)
                    y: height / 2,
                    angle: baseAngle,
                    dist: dist,
                    size: Math.random() * particleSize + 1,
                    color: color,
                    phaseX: Math.random() * Math.PI * 2,
                    phaseY: Math.random() * Math.PI * 2,
                });
            }
            particlesRef.current = particles;
        };

        init();

        const animate = () => {
            ctx.clearRect(0, 0, width, height);
            timeRef.current += 0.02;
            rotationRef.current += speed;

            const centerX = width / 2;
            const centerY = height / 2;

            particlesRef.current.forEach((particle) => {
                // wyliczenie pozycji bazowej na podstawie rotacji
                const currentAngle = particle.angle + rotationRef.current;
                const baseX = centerX + Math.cos(currentAngle) * particle.dist;
                const baseY = centerY + Math.sin(currentAngle) * particle.dist;

                // prosta „fizyka” interakcji z myszą
                let dx = mouseRef.current.x - particle.x;
                let dy = mouseRef.current.y - particle.y;
                let distance = Math.sqrt(dx * dx + dy * dy);
                let forceDirectionX = dx / distance;
                let forceDirectionY = dy / distance;

                let maxDistance = mouseRadius;
                let force = (maxDistance - distance) / maxDistance;
                let directionX = forceDirectionX * force * mouseStrength;
                let directionY = forceDirectionY * force * mouseStrength;

                // ruch ambient: delikatne „falowanie”
                const ambientX = Math.sin(timeRef.current + particle.phaseX) * 2;
                const ambientY = Math.cos(timeRef.current + particle.phaseY) * 2;

                const targetX = baseX + ambientX;
                const targetY = baseY + ambientY;

                if (distance < mouseRadius && mouseRef.current.active) {
                    particle.x -= directionX;
                    particle.y -= directionY;
                } else {
                    // powrót do pozycji bazowej
                    if (particle.x !== targetX) {
                        let dx = particle.x - targetX;
                        particle.x -= dx / 10;
                    }
                    if (particle.y !== targetY) {
                        let dy = particle.y - targetY;
                        particle.y -= dy / 10;
                    }
                }

                // rysowanie cząsteczki
                ctx.fillStyle = particle.color;
                ctx.beginPath();
                ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
                ctx.closePath();
                ctx.fill();
            });

            animationRef.current = requestAnimationFrame(animate);
        };

        animate();

        const handleMouseMove = (e: MouseEvent) => {
            const rect = canvas.getBoundingClientRect();
            mouseRef.current.x = e.clientX - rect.left;
            mouseRef.current.y = e.clientY - rect.top;
            mouseRef.current.active = true;
        };

        const handleMouseLeave = () => {
            mouseRef.current.active = false;
        };

        canvas.addEventListener("mousemove", handleMouseMove);
        canvas.addEventListener("mouseleave", handleMouseLeave);
        window.addEventListener("resize", init);

        return () => {
            if (animationRef.current) cancelAnimationFrame(animationRef.current);
            canvas.removeEventListener("mousemove", handleMouseMove);
            canvas.removeEventListener("mouseleave", handleMouseLeave);
            window.removeEventListener("resize", init);
        };
    }, [colors, particleSize, mouseRadius, mouseStrength, radius, count, speed]);

    return (
        <canvas
            ref={canvasRef}
            className={className}
            style={{ width: '100%', height: '100%' }}
        />
    );
}
