"use client";

import React, { useEffect, useState } from "react";
import ParticleText from "@/components/ui/ParticleText";

type GalleryItem = {
  id: string;
  title: string;
  description?: string;
  soundcloud_url: string;
  tags?: string[];
  year?: number | null;
};

function buildSoundCloudEmbedSrc(soundcloudUrl: string): string {
  const base = "https://w.soundcloud.com/player/";
  const url = encodeURIComponent(soundcloudUrl);
  // Compact player to avoid huge embeds.
  return `${base}?url=${url}&auto_play=false&show_teaser=false&visual=false&hide_related=true&show_comments=false&show_user=true&show_reposts=false`;
}

const FALLBACK_ITEMS: GalleryItem[] = [
  {
    id: "demo-01",
    title: "Cinematic Pulse (Demo)",
    description:
      "Przykładowy utwór pokazujący jak brzmią generowane sample po miksie/masterze w DAW. (placeholder)",
    soundcloud_url: "https://soundcloud.com/forss/flickermood",
    tags: ["cinematic", "mix/master"],
    year: 2025,
  },
  {
    id: "demo-02",
    title: "Lo-fi Groove Sketch (Demo)",
    description: "Luźny szkic: groove + tekstury. (placeholder)",
    soundcloud_url: "https://soundcloud.com/forss/stranger",
    tags: ["lofi", "groove"],
    year: 2025,
  },
  {
    id: "demo-03",
    title: "Tech House Drop (Demo)",
    description: "Krótka prezentacja transjentów i subu po obróbce. (placeholder)",
    soundcloud_url: "https://soundcloud.com/forss/sets/ecclesia",
    tags: ["club"],
    year: 2025,
  },
];

export default function GalleryPage() {
  const [items, setItems] = useState<GalleryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      try {
        const API_BASE =
          process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
        const resp = await fetch(`${API_BASE}/api/air/gallery/items`, {
          method: "GET",
          headers: { Accept: "application/json" },
        });
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const data = (await resp.json()) as { items?: GalleryItem[] };
        const next = Array.isArray(data?.items) ? data.items : [];
        setItems(next);
        setError(null);
      } catch (e) {
        setItems(FALLBACK_ITEMS);
        setError(
          "Nie udało się pobrać galerii z backendu — pokazuję pozycje przykładowe."
        );
      }
    };

    run();
  }, []);

  const resolvedItems = items ?? FALLBACK_ITEMS;

  return (
    <section className="min-h-screen bg-gradient-to-b from-pink-500/10 via-purple-500/10 to-cyan-500/10 p-6 md:p-10">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="bg-gradient-to-r from-pink-500/10 via-purple-500/10 to-cyan-500/10 border border-white/10 rounded-2xl shadow-lg shadow-purple-900/10 p-6 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-b from-white/10 to-transparent pointer-events-none" />

          <div className="relative z-10 space-y-4">
            <div className="h-24 md:h-32 w-full">
              <ParticleText
                text="GALLERY"
                colors={["#ff0080", "#ff8c00", "#ffee00", "#00ff85", "#00c3ff", "#7a00ff"]}
                font="bold 74px system-ui"
                particleSize={2}
                mouseRadius={20}
                mouseStrength={25}
              />
            </div>

            <p className="text-sm text-gray-200 text-center mx-auto">
              Portfolio customowych audio — przykłady tego, co da się wyciągnąć z
              generowanych próbek po miksie/masterze w DAW.
            </p>

            {error && (
              <div className="text-xs text-amber-300/90 text-center">{error}</div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6">
          {resolvedItems.map((item) => (
            <article
              key={item.id}
              className="bg-gradient-to-br from-pink-500/10 via-purple-500/10 to-cyan-500/10 border border-white/10 rounded-2xl p-4 md:p-6"
            >
              <header className="flex flex-col gap-2 mb-4">
                <div className="flex items-baseline justify-between gap-4 flex-wrap">
                  <h2 className="text-lg md:text-xl text-white font-semibold">
                    {item.title}
                  </h2>
                  {item.year ? (
                    <div className="text-xs text-gray-100/80">{item.year}</div>
                  ) : null}
                </div>

                {item.description ? (
                  <p className="text-sm text-gray-100/90 leading-relaxed">
                    {item.description}
                  </p>
                ) : null}

                {item.tags && item.tags.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {item.tags.map((t) => (
                      <span
                        key={t}
                        className="text-[11px] text-gray-100/90 border border-white/15 rounded-full px-2 py-0.5 bg-black/20"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                ) : null}
              </header>

              <div className="w-full">
                <div className="relative w-full overflow-hidden rounded-xl border border-white/10 bg-black/40">
                  <iframe
                    title={item.title}
                    className="w-full"
                    height={166}
                    scrolling="no"
                    frameBorder="no"
                    allow="autoplay"
                    loading="lazy"
                    src={buildSoundCloudEmbedSrc(item.soundcloud_url)}
                  />
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
