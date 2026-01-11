"use client";

// stopka aplikacji: stały podpis / wersja w dolnej części layoutu.

export default function Footer() {
  return (
    <footer className="shade w-full text-center text-xs md:text-sm opacity-70 hover:opacity-100 transition-opacity mt-auto py-3 border-t border-white/10 bg-black/30 backdrop-blur-sm">
      <p className="tracking-wide">Michał Dyjak - Artificial Intelligence Resampler v4.2</p>
    </footer>
  );
}
