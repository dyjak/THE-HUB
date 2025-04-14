"use client";

import Link from "next/link";
import StarBackground from "@/components/ui/StarBackground";
import { useSession, signOut } from "next-auth/react";

export default function Layout({ children }: { children: React.ReactNode }) {
    const { data: session } = useSession();

    return (
        <div className="relative min-h-screen flex flex-col bg-transparent text-white">
            <StarBackground />
            <nav className="p-4 bg-gray-900 flex justify-between items-center relative z-10">
                <div className="flex gap-4">
                    <Link href="/" className="text-xl hover:text-gray-300">🏠 Home</Link>
                    <Link href="/app1" className="text-xl hover:text-gray-300">🎵 App1</Link>
                    <Link href="/app2" className="text-xl hover:text-gray-300">🎶 App2</Link>
                    <Link href="/air" className="text-xl hover:text-gray-300">🚀 AIR</Link>
                </div>
                <div>
                    {session ? (
                        <div className="flex items-center gap-4">
                            <span>Witaj, {session.user?.name}</span>
                            <button
                                onClick={() => signOut({ callbackUrl: '/' })}
                                className="px-4 py-2 border border-red-500 rounded-lg hover:bg-red-800 transition-colors"
                            >
                                Wyloguj
                            </button>
                        </div>
                    ) : (
                        <Link
                            href="/login"
                            className="px-4 py-2 border border-blue-500 rounded-lg hover:bg-blue-800 transition-colors"
                        >
                            Zaloguj
                        </Link>
                    )}
                </div>
            </nav>
            <main className="flex-grow p-6 relative z-10 bg-transparent">{children}</main>
        </div>
    );
}