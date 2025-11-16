"use client";
import React, { useEffect, useRef, useState, useCallback } from 'react';

interface SimpleAudioPlayerProps {
  src: string;
  className?: string;
  height?: number;
  preload?: 'auto' | 'metadata' | 'none';
}

// Lightweight custom audio player: play/pause, progress bar, current/total time, volume.
// No external dependencies; SSR-safe via client directive.
export const SimpleAudioPlayer: React.FC<SimpleAudioPlayerProps> = ({ src, className = '', height = 32, preload = 'metadata' }) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const progressRef = useRef<HTMLDivElement | null>(null);
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [current, setCurrent] = useState(0);
  const [volume, setVolume] = useState(1);

  const toggle = useCallback(() => {
    const el = audioRef.current; if (!el || !ready) return;
    if (el.paused) { el.play(); setPlaying(true); } else { el.pause(); setPlaying(false); }
  }, [ready]);

  const fmt = (sec: number) => {
    if (!Number.isFinite(sec)) return '0:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2,'0')}`;
  };

  useEffect(() => {
    const el = audioRef.current; if (!el) return;
    const onLoaded = () => { setDuration(el.duration || 0); setReady(true); };
    const onTime = () => { setCurrent(el.currentTime || 0); };
    const onEnded = () => { setPlaying(false); setCurrent(el.duration || 0); };
    el.addEventListener('loadedmetadata', onLoaded);
    el.addEventListener('timeupdate', onTime);
    el.addEventListener('ended', onEnded);
    return () => {
      el.removeEventListener('loadedmetadata', onLoaded);
      el.removeEventListener('timeupdate', onTime);
      el.removeEventListener('ended', onEnded);
    };
  }, [src]);

  const seek = useCallback((e: React.MouseEvent) => {
    const bar = progressRef.current; const el = audioRef.current;
    if (!bar || !el || duration <= 0) return;
    const rect = bar.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const ratio = Math.min(Math.max(x / rect.width, 0), 1);
    el.currentTime = ratio * duration;
    setCurrent(el.currentTime);
  }, [duration]);

  useEffect(() => {
    const el = audioRef.current; if (!el) return;
    el.volume = volume;
  }, [volume]);

  return (
    <div className={`flex items-center gap-2 ${className}`} style={{ height }}>
      <audio ref={audioRef} src={src} preload={preload} className="hidden" />
      <button
        onClick={toggle}
        className={`w-8 h-8 flex items-center justify-center rounded bg-black/50 border border-gray-700 text-xs hover:bg-black/60 ${ready ? '' : 'opacity-50 cursor-not-allowed'}`}
        title={playing ? 'Pause' : 'Play'}
        disabled={!ready}
      >{playing ? '❚❚' : '►'}</button>
      <div className="flex-1 flex flex-col gap-1">
        <div
          ref={progressRef}
          onClick={seek}
          className="relative h-2 bg-gray-700 rounded cursor-pointer group"
        >
          <div
            className="absolute top-0 left-0 h-2 bg-emerald-500 rounded group-hover:bg-emerald-400 transition-colors"
            style={{ width: duration > 0 ? `${(current / duration) * 100}%` : '0%' }}
          />
        </div>
        <div className="flex justify-between text-[10px] font-mono text-gray-400">
          <span>{fmt(current)}</span>
          <span>{fmt(duration)}</span>
        </div>
      </div>
      <div className="flex items-center gap-1 w-24">
        <span className="text-[10px] text-gray-500">vol</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={volume}
          onChange={e => setVolume(Number(e.target.value))}
          className="flex-1"
        />
      </div>
    </div>
  );
};
