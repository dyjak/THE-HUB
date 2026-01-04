"use client";

// layout dla modułu air.
// moduł air jest „za logowaniem”, więc ten layout pilnuje sesji i robi redirect na /login,
// a dopiero potem renderuje właściwą zawartość podstron.

import { ReactNode, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

export default function AirLayout({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    // jeśli nie ma sesji, przekierowujemy na stronę logowania.
    // robimy to w efekcie, bo na app-routerze redirect po stronie klienta
    // musi mieć dostęp do routera.
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
    // czekamy aż useeffect zadziała i przeniesie na /login.
    // zwracamy null, żeby nie „mignęła” treść air bez autoryzacji.
    return null;
  }

  return <>{children}</>;
}
