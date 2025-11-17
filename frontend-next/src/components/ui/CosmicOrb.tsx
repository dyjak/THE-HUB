"use client";

import React, { useRef, useEffect } from "react";

export interface CosmicOrbProps {
  className?: string;
  width?: number;
  height?: number;
  particleCount?: number;
  colors?: string[];
  background?: string;
}

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  color: string;
};

export default function CosmicOrb({
  className = "",
  width,
  height,
  particleCount = 380,
  // colors = ["#90e0ef", "#ade8f4", "#caf0f8"],
  colors = ["#0096c7", "#023e8a", "#0077b6"],

  background = "transparent",
}: CosmicOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const particlesRef = useRef<Particle[]>([]);
  const animRef = useRef<number | null>(null);
  const hoveredRef = useRef(false);
  const mouseRef = useRef({ x: 0, y: 0 });

  const rand = (min: number, max: number) => Math.random() * (max - min) + min;

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const parent = canvas.parentElement;
      const w = width ?? (parent ? parent.clientWidth : window.innerWidth);
      const h = height ?? (parent ? parent.clientHeight : window.innerHeight);
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    resize();
    const ro = new ResizeObserver(resize);
    if (canvas.parentElement) ro.observe(canvas.parentElement);

    // init particles: start ściśnięte w centrum
    const rect = canvas.getBoundingClientRect();
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    particlesRef.current = Array.from({ length: particleCount }, () => ({
      x: cx + rand(-10, 10),
      y: cy + rand(-10, 10),
      vx: rand(-0.05, 0.05),
      vy: rand(-0.05, 0.05),
      r: rand(2, 4),
      // ensure color is valid CSS format
      color: colors[Math.floor(Math.random() * colors.length)].replace(/[^#a-fA-F0-9]/g, ''),
    }));

    const onMove = (e: MouseEvent) => {
      const r = canvas.getBoundingClientRect();
      mouseRef.current.x = e.clientX - r.left;
      mouseRef.current.y = e.clientY - r.top;
    };

    const onEnter = (e: MouseEvent) => { hoveredRef.current = true; onMove(e); };
    const onLeave = () => { hoveredRef.current = false; };

    canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("mouseenter", onEnter);
    canvas.addEventListener("mouseleave", onLeave);

    const hoverRadius = 120;
    const hoverStrength = 0.02;
    const cohesionStrength = 0.00001;
    const separationStrength = 0.015;
    const centerPull = 0.007;
    const maxSpeed = 0.5;

    const step = () => {
      const rect = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);
      const particles = particlesRef.current;
      const mouse = mouseRef.current;
      const hovering = hoveredRef.current;

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        const dx = mouse.x - p.x;
        const dy = mouse.y - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy) + 0.001;
        if (hovering && dist < hoverRadius) {
          p.vx += (dx / dist) * hoverStrength;
          p.vy += (dy / dist) * hoverStrength;
        }

        for (let j = i + 1; j < particles.length; j++) {
          const q = particles[j];
          const rx = q.x - p.x;
          const ry = q.y - p.y;
          const rd = Math.sqrt(rx * rx + ry * ry) + 0.001;
          if (hovering) {
            const coh = cohesionStrength * (1 - Math.min(rd / hoverRadius, 1));
            p.vx += (rx / rd) * coh;
            p.vy += (ry / rd) * coh;
            q.vx -= (rx / rd) * coh;
            q.vy -= (ry / rd) * coh;
          } else if (rd < 15) {
            const sep = separationStrength * (1 - rd / 15);
            p.vx -= (rx / rd) * sep;
            p.vy -= (ry / rd) * sep;
            q.vx += (rx / rd) * sep;
            q.vy += (ry / rd) * sep;
          }
        }

        const cx = rect.width / 2, cy = rect.height / 2;
        const dx2 = cx - p.x, dy2 = cy - p.y;
        const d2 = Math.sqrt(dx2 * dx2 + dy2 * dy2) + 0.001;
        p.vx += (dx2 / d2) * centerPull;
        p.vy += (dy2 / d2) * centerPull;

        p.vx *= 0.985;
        p.vy *= 0.985;
        const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
        if (speed > maxSpeed) {
          p.vx = (p.vx / speed) * maxSpeed;
          p.vy = (p.vy / speed) * maxSpeed;
        }

        p.x += p.vx;
        p.y += p.vy;
        if (p.x < p.r) { p.x = p.r; p.vx *= -0.3; }
        if (p.x > rect.width - p.r) { p.x = rect.width - p.r; p.vx *= -0.3; }
        if (p.y < p.r) { p.y = p.r; p.vy *= -0.3; }
        if (p.y > rect.height - p.r) { p.y = rect.height - p.r; p.vy *= -0.3; }

        const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 6);
        grad.addColorStop(0, p.color);
        grad.addColorStop(0.3, p.color + "55".slice(0, 2)); // only valid hex alpha
        grad.addColorStop(1, "rgba(0,0,0,0)");
        ctx.beginPath();
        ctx.fillStyle = grad as unknown as string;
        ctx.arc(p.x, p.y, p.r * 2.2, 0, Math.PI * 2);
        ctx.fill();
      }

      animRef.current = requestAnimationFrame(step);
    };

    animRef.current = requestAnimationFrame(step);

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
      canvas.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("mouseenter", onEnter);
      canvas.removeEventListener("mouseleave", onLeave);
      ro.disconnect();
    };
  }, [particleCount, colors, width, height, background]);

  return <canvas ref={canvasRef} className={className} style={{ display: "block", width: "100%", height: "100%" }} />;
}