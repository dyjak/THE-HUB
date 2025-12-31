"use client";

import React, { useLayoutEffect, useMemo, useRef, useEffect, useState } from "react";

interface ParticleTextProps {
  text?: string;
  className?: string;
  colors?: string[];
  particleSize?: number;
  mouseRadius?: number;
  mouseStrength?: number;
  font?: string;
}

interface Particle {
  x: number;
  y: number;
  baseX: number;
  baseY: number;
  size: number;
  density: number;
  color: string;
  phaseX: number;
  phaseY: number;
}

export default function ParticleText({
  text = "AIR 4.2",
  className = "",
  colors = ["#0096c7", "#023e8a", "#0077b6", "#ffffff"],
  particleSize = 2,
  mouseRadius = 60,
  mouseStrength = 20,
  font = "bold 120px system-ui",
}: ParticleTextProps) {
  const [usePlainText, setUsePlainText] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const measureRef = useRef<HTMLSpanElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const particlesRef = useRef<Particle[]>([]);
  const mouseRef = useRef({ x: 0, y: 0, active: false });
  const animationRef = useRef<number | null>(null);
  const timeRef = useRef(0);

  const fallbackTextStyle = useMemo(() => {
    const base: React.CSSProperties = {
      lineHeight: 1,
      whiteSpace: "nowrap",
      textAlign: "center",
      width: "100%",
    };

    // Handle common patterns used in this repo:
    // - "bold 74px system-ui"
    // - "bold clamp(28px, 8vw, 64px) system-ui" (not valid as canvas font, but usable as CSS fontSize)
    if (font.includes("clamp(")) {
      const clampStart = font.indexOf("clamp(");
      const weightPart = font.slice(0, clampStart).trim();
      const closeIdx = font.indexOf(")", clampStart);
      const sizePart = closeIdx === -1 ? font.slice(clampStart) : font.slice(clampStart, closeIdx + 1);
      const familyPart = closeIdx === -1 ? "system-ui" : font.slice(closeIdx + 1).trim();

      return {
        ...base,
        fontWeight: weightPart || "bold",
        fontSize: sizePart,
        fontFamily: familyPart || "system-ui",
      };
    }

    const match = font.match(/^(\w+|\d{3})\s+(\d+(?:\.\d+)?)px\s+(.+)$/);
    if (match) {
      return {
        ...base,
        fontWeight: match[1],
        fontSize: `${match[2]}px`,
        fontFamily: match[3],
      };
    }

    return {
      ...base,
      font: font,
    };
  }, [font]);

  useLayoutEffect(() => {
    const container = containerRef.current;
    const measureEl = measureRef.current;
    if (!container || !measureEl) return;

    const update = () => {
      const containerWidth = container.clientWidth;
      const containerHeight = container.clientHeight;

      // If we have no room, fall back to plain text.
      if (containerWidth <= 0 || containerHeight <= 0) {
        setUsePlainText(true);
        return;
      }

      // Measure the natural one-line width of the text using DOM (supports clamp() fontSize).
      // Use scrollWidth so it ignores container width constraints.
      const textWidth = measureEl.scrollWidth;

      // Small padding to avoid edge clipping.
      const fits = textWidth <= containerWidth * 0.98;
      setUsePlainText(!fits);
    };

    update();

    const ro = new ResizeObserver(() => update());
    ro.observe(container);
    window.addEventListener("resize", update);

    return () => {
      ro.disconnect();
      window.removeEventListener("resize", update);
    };
  }, [text, fallbackTextStyle]);

  useEffect(() => {
    if (usePlainText) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = canvas.width;
    let height = canvas.height;

    const init = () => {
      // Resize canvas to parent
      const parent = canvas.parentElement;
      if (parent) {
        canvas.width = parent.clientWidth;
        canvas.height = parent.clientHeight;
      }
      width = canvas.width;
      height = canvas.height;

      // Draw text to get coordinates
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "white";
      // Prefer computed CSS font from our measure element (handles clamp() etc.)
      const measuredCssFont = measureRef.current ? window.getComputedStyle(measureRef.current).font : "";
      ctx.font = measuredCssFont || font;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(text, width / 2, height / 2);

      const textData = ctx.getImageData(0, 0, width, height);
      const particles: Particle[] = [];

      // Sampling step - adjust for performance vs density
      const step = 4;

      for (let y = 0; y < height; y += step) {
        for (let x = 0; x < width; x += step) {
          const index = (y * width + x) * 4;
          const alpha = textData.data[index + 3];

          if (alpha > 128) {
            const color = colors[Math.floor(Math.random() * colors.length)];
            particles.push({
              x: Math.random() * width,
              y: Math.random() * height,
              baseX: x,
              baseY: y,
              size: particleSize,
              density: (Math.random() * 30) + 1,
              color: color,
              phaseX: Math.random() * Math.PI * 2,
              phaseY: Math.random() * Math.PI * 2,
            });
          }
        }
      }
      particlesRef.current = particles;
    };

    init();

    const animate = () => {
      ctx.clearRect(0, 0, width, height);
      timeRef.current += 0.02;

      particlesRef.current.forEach((particle, index) => {
        let dx = mouseRef.current.x - particle.x;
        let dy = mouseRef.current.y - particle.y;
        let distance = Math.sqrt(dx * dx + dy * dy);
        if (distance === 0) distance = 0.0001;
        let forceDirectionX = dx / distance;
        let forceDirectionY = dy / distance;

        // Mouse interaction
        let maxDistance = mouseRadius;
        let force = (maxDistance - distance) / maxDistance;
        let directionX = forceDirectionX * force * mouseStrength;
        let directionY = forceDirectionY * force * mouseStrength;

        // Ambient motion (living particles)
        // Use random phase to make them move independently
        const ambientX = Math.sin(timeRef.current + particle.phaseX) * 1.5;
        const ambientY = Math.cos(timeRef.current + particle.phaseY) * 1.5;

        const targetX = particle.baseX + ambientX;
        const targetY = particle.baseY + ambientY;

        if (distance < mouseRadius && mouseRef.current.active) {
          particle.x -= directionX;
          particle.y -= directionY;
        } else {
          // Return to base (with ambient offset)
          if (particle.x !== targetX) {
            let dx = particle.x - targetX;
            particle.x -= dx / 15; // Slower return for smoother feel
          }
          if (particle.y !== targetY) {
            let dy = particle.y - targetY;
            particle.y -= dy / 15;
          }
        }

        // Draw particle
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
  }, [usePlainText, text, colors, font, mouseRadius, mouseStrength, particleSize]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ width: "100%", height: "100%", position: "relative" }}
    >
      {/* Hidden measurer: determines if the text fits the container at current CSS font */}
      <span
        ref={measureRef}
        aria-hidden="true"
        style={{
          ...fallbackTextStyle,
          position: "absolute",
          visibility: "hidden",
          pointerEvents: "none",
          width: "auto",
          left: 0,
          top: 0,
        }}
      >
        {text}
      </span>

      {usePlainText ? (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span
            style={{
              ...fallbackTextStyle,
              display: "inline-block",
              transform: "scale(0.6)",
              transformOrigin: "center",
            }}
          >
            {text}
          </span>
        </div>
      ) : (
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%" }} />
      )}
    </div>
  );
}
