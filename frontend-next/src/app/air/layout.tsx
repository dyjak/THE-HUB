"use client";

import { ReactNode, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

export default function AirLayout({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <main className="min-h-screen flex items-center justify-center bg-black text-white">
        <div className="text-sm text-gray-300">Ładowanie sesji...</div>
      </main>
    );
  }

  if (!session) {
    // Czekamy aż useEffect zadziała i przeniesie na /login
    return null;
  }

  return <>{children}</>;
}
