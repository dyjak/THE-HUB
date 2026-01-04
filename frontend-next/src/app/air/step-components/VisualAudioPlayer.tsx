"use client";

/*
    odtwarzacz audio z prostą wizualizacją widma (paski na canvasie).

    co robi:
    - steruje elementem <audio> (play/pause, głośność, przewijanie)
    - tworzy audio context + analyser node, żeby pobierać dane o częstotliwościach
    - rysuje animowany wizualizer na canvasie tylko w trakcie odtwarzania

    ważne uwagi:
    - audio context w przeglądarce zwykle wymaga "gestu użytkownika" (klik), więc tworzymy go przy pierwszym odtworzeniu
    - requestAnimationFrame jest zatrzymywany, gdy audio nie gra (żeby oszczędzać zasoby)
*/
import React, { useEffect, useRef, useState, useCallback } from "react";

interface VisualAudioPlayerProps {
    src: string;
    className?: string;
    title?: string;
    accentColor?: string;
    accentColor2?: string; // kolor pasków wizualizera
}

export const VisualAudioPlayer: React.FC<VisualAudioPlayerProps> = ({
    src,
    className = "",
    title,
    accentColor = "#ef4444",
    accentColor2 = "#634bffff", // domyślny kolor pasków wizualizera
}) => {
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const progressRef = useRef<HTMLDivElement | null>(null);
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const animationRef = useRef<number | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
    const barPropsRef = useRef<{ widthMult: number }[]>([]);

    const [ready, setReady] = useState(false);
    const [playing, setPlaying] = useState(false);
    const [duration, setDuration] = useState(0);
    const [current, setCurrent] = useState(0);
    const [volume, setVolume] = useState(0.75);

    // inicjalizuje web audio (audio context + analyser) i podpina <audio> jako źródło.
    // robimy to tylko raz, przy pierwszym użyciu, bo createMediaElementSource nie może być tworzony wielokrotnie dla tego samego elementu.
    const setupAudioContext = useCallback(() => {
        const audio = audioRef.current;
        if (!audio || audioContextRef.current) return;

        try {
            const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
            const analyser = ctx.createAnalyser();
            analyser.fftSize = 128;
            analyser.smoothingTimeConstant = 0.8;

            const source = ctx.createMediaElementSource(audio);
            source.connect(analyser);
            analyser.connect(ctx.destination);

            audioContextRef.current = ctx;
            analyserRef.current = analyser;
            sourceRef.current = source;
        } catch (e) {
            console.warn("Audio context setup failed:", e);
        }
    }, []);

    // uruchamia pętlę rysowania wizualizera.
    // analyser.getByteFrequencyData zwraca "głośność" w pasmach częstotliwości (0-255).
    // na tej podstawie rysujemy pionowe słupki na canvasie.
    const drawVisualizer = useCallback(() => {
        const canvas = canvasRef.current;
        const analyser = analyserRef.current;
        if (!canvas || !analyser) return;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const barColor = accentColor2.length > 7 ? accentColor2.slice(0, 7) : accentColor2;
        const bufferLength = analyser.frequencyBinCount;

        // przechowujemy losowe mnożniki szerokości słupków w refie, żeby wizualizer wyglądał "żywiej",
        // ale jednocześnie był stabilny w trakcie jednego odtwarzania.
        if (barPropsRef.current.length !== bufferLength) {
            barPropsRef.current = Array.from({ length: bufferLength }, () => ({
                widthMult: 0.2 + Math.random() * 1.0,
            }));
        }

        const draw = () => {
            if (!playing) {
                animationRef.current = null;
                return;
            }

            animationRef.current = requestAnimationFrame(draw);

            const dataArray = new Uint8Array(bufferLength);
            analyser.getByteFrequencyData(dataArray);

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const baseWidth = canvas.width / bufferLength;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                const props = barPropsRef.current[i];
                const barWidth = Math.max(1, baseWidth * props.widthMult);
                const barHeight = (dataArray[i] / 255) * canvas.height * 0.95;

                if (barHeight < 2) {
                    x += barWidth + 1;
                    continue;
                }

                const gradient = ctx.createLinearGradient(0, canvas.height, 0, canvas.height - barHeight);
                gradient.addColorStop(0, barColor);
                gradient.addColorStop(0.3, barColor + "dd");
                gradient.addColorStop(0.6, barColor + "88");
                gradient.addColorStop(1, barColor + "20");

                ctx.fillStyle = gradient;
                ctx.beginPath();
                const radius = Math.min(barWidth / 2, 2);
                const y = canvas.height - barHeight;

                ctx.moveTo(x + radius, y);
                ctx.lineTo(x + barWidth - radius, y);
                ctx.quadraticCurveTo(x + barWidth, y, x + barWidth, y + radius);
                ctx.lineTo(x + barWidth, canvas.height);
                ctx.lineTo(x, canvas.height);
                ctx.lineTo(x, y + radius);
                ctx.quadraticCurveTo(x, y, x + radius, y);
                ctx.closePath();
                ctx.fill();

                ctx.shadowColor = barColor;
                ctx.shadowBlur = 3;

                x += barWidth + 1;
            }

            ctx.shadowBlur = 0;
        };

        draw();
    }, [playing, accentColor]);

    // gdy włączamy odtwarzanie, startujemy rysowanie; gdy wyłączamy, sprzątamy requestAnimationFrame.
    useEffect(() => {
        if (playing && analyserRef.current) {
            drawVisualizer();
        }
        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
        };
    }, [playing, drawVisualizer]);

    // play/pause.
    // dodatkowo: przy pierwszym kliknięciu inicjalizujemy audio context, a gdy jest "suspended" (częste w przeglądarkach), wznawiamy go.
    const toggle = useCallback(() => {
        const el = audioRef.current;
        if (!el || !ready) return;

        if (!audioContextRef.current) {
            setupAudioContext();
        }

        if (audioContextRef.current?.state === "suspended") {
            audioContextRef.current.resume();
        }

        if (el.paused) {
            el.play();
            setPlaying(true);
        } else {
            el.pause();
            setPlaying(false);
        }
    }, [ready, setupAudioContext]);

    const fmt = (sec: number) => {
        if (!Number.isFinite(sec)) return "0:00";
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return `${m}:${s.toString().padStart(2, "0")}`;
    };

    // podpina zdarzenia z elementu <audio> do stanu reactowego.
    useEffect(() => {
        const el = audioRef.current;
        if (!el) return;
        const onLoaded = () => {
            setDuration(el.duration || 0);
            setReady(true);
        };
        const onTime = () => {
            setCurrent(el.currentTime || 0);
        };
        const onEnded = () => {
            setPlaying(false);
            setCurrent(el.duration || 0);
        };
        el.addEventListener("loadedmetadata", onLoaded);
        el.addEventListener("timeupdate", onTime);
        el.addEventListener("ended", onEnded);
        return () => {
            el.removeEventListener("loadedmetadata", onLoaded);
            el.removeEventListener("timeupdate", onTime);
            el.removeEventListener("ended", onEnded);
        };
    }, [src]);

    // przewijanie po kliknięciu w pasek postępu (tak jak w prostszym odtwarzaczu).
    const seek = useCallback(
        (e: React.MouseEvent) => {
            const bar = progressRef.current;
            const el = audioRef.current;
            if (!bar || !el || duration <= 0) return;
            const rect = bar.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const ratio = Math.min(Math.max(x / rect.width, 0), 1);
            el.currentTime = ratio * duration;
            setCurrent(el.currentTime);
        },
        [duration]
    );

    // synchronizuje suwak głośności z elementem <audio>.
    useEffect(() => {
        const el = audioRef.current;
        if (!el) return;
        el.volume = volume;
    }, [volume]);

    // sprzątanie po odmontowaniu: zatrzymujemy animację i zamykamy audio context.
    useEffect(() => {
        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
            if (audioContextRef.current) {
                audioContextRef.current.close();
            }
        };
    }, []);

    const progressPercent = duration > 0 ? (current / duration) * 100 : 0;

    return (
        <div
            className={`relative bg-black/60 border border-gray-800/60 rounded-2xl overflow-hidden backdrop-blur-sm ${className}`}
            style={{ "--accent": accentColor } as React.CSSProperties}
        >
            <audio ref={audioRef} src={src} preload="metadata" className="hidden" crossOrigin="anonymous" />

            <div className="absolute inset-0 opacity-40 pointer-events-none">
                <canvas ref={canvasRef} width={400} height={80} className="w-full h-full" />
            </div>

            <div className="absolute top-0 right-0 z-20 flex items-center gap-0 opacity-80 hover:opacity-100 transition-opacity scale-75">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-6 h-6 text-gray-400">
                    <path d="M10 3.75a.75.75 0 00-1.264-.546L4.703 7H3.167a.75.75 0 00-.7.48A6.985 6.985 0 002 10c0 .887.165 1.737.468 2.52.111.29.39.48.7.48h1.535l4.033 3.796A.75.75 0 0010 16.25V3.75z" />
                </svg>
                <div className="h-16 flex items-center justify-center">
                    <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.05}
                        value={volume}
                        onChange={(e) => setVolume(Number(e.target.value))}
                        className="accent-gray-400 cursor-pointer"
                        title={`Głośność: ${Math.round(volume * 100)}%`}
                    />
                </div>
            </div>

            <div className="relative z-10 p-4 pr-8">
                {title && (
                    <div className="text-sm font-bold mb-3 truncate" style={{ color: accentColor }}>
                        {title}
                    </div>
                )}

                <div className="flex items-center gap-4">
                    <button
                        onClick={toggle}
                        disabled={!ready}
                        className={`relative w-14 h-14 flex items-center justify-center rounded-full transition-all duration-300 ${ready
                            ? "bg-gradient-to-br from-gray-800 to-gray-900 hover:scale-105 hover:shadow-lg cursor-pointer"
                            : "bg-gray-800/50 cursor-not-allowed opacity-50"
                            }`}
                        style={{
                            boxShadow: playing ? `0 0 20px ${accentColor}40` : undefined,
                            border: `2px solid ${playing ? accentColor : "rgba(255,255,255,0.1)"}`,
                        }}
                        title={playing ? "Pauza" : "Odtwórz"}
                    >
                        {playing ? (
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6" style={{ color: accentColor }}>
                                <path fillRule="evenodd" d="M6.75 5.25a.75.75 0 01.75-.75H9a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H7.5a.75.75 0 01-.75-.75V5.25zm7.5 0A.75.75 0 0115 4.5h1.5a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H15a.75.75 0 01-.75-.75V5.25z" clipRule="evenodd" />
                            </svg>
                        ) : (
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 ml-1" style={{ color: accentColor }}>
                                <path fillRule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" />
                            </svg>
                        )}

                        {playing && (
                            <span
                                className="absolute inset-0 rounded-full animate-ping opacity-20"
                                style={{ backgroundColor: accentColor }}
                            />
                        )}
                    </button>

                    <div className="flex-1 space-y-2">
                        <div
                            ref={progressRef}
                            onClick={seek}
                            className="relative h-3 bg-gray-800 rounded-full cursor-pointer group overflow-hidden"
                        >
                            <div
                                className="absolute top-0 left-0 h-full rounded-full transition-all duration-100"
                                style={{
                                    width: `${progressPercent}%`,
                                    background: `linear-gradient(90deg, ${accentColor}80, ${accentColor})`,
                                }}
                            />

                            <div
                                className="absolute top-0 left-0 h-full rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                                style={{
                                    width: `${progressPercent}%`,
                                    background: `linear-gradient(90deg, ${accentColor}40, ${accentColor}80)`,
                                    filter: "blur(4px)",
                                }}
                            />

                            <div
                                className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 shadow-lg"
                                style={{
                                    left: `calc(${progressPercent}% - 8px)`,
                                    backgroundColor: accentColor,
                                    boxShadow: `0 0 10px ${accentColor}`,
                                }}
                            />
                        </div>

                        <div className="flex justify-between text-[11px] font-mono text-gray-400">
                            <span style={{ color: accentColor }}>{fmt(current)}</span>
                            <span>{fmt(duration)}</span>
                        </div>
                    </div>
                </div>
            </div>

            <div
                className="absolute bottom-0 left-0 right-0 h-0.5"
                style={{
                    background: `linear-gradient(90deg, transparent, ${accentColor}60, transparent)`,
                }}
            />
        </div>
    );
};
