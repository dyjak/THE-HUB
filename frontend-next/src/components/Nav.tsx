"use client";

// nawigacja górna: linki do głównych sekcji oraz stan logowania.
// - gdy jest sesja: pokazuje powitanie i przycisk wylogowania,
// - gdy brak sesji: pokazuje link do logowania.
// uwaga: zakomentowane linki niżej to starsze skróty / szkice z początków projektu.

import Link from "next/link";
import { useSession, signOut } from "next-auth/react";
import { FaHome, FaGithub, FaBrain, FaUser } from "react-icons/fa";


export default function Nav() {
    const { data: session } = useSession();

    return (
        <nav className="shade p-2 bg-black flex justify-around items-center relative z-10">
            <div className="flex gap-4 items-center">
                {/*<Link href="/" className="text-m hover:text-gray-300">🏠 home (stary skrót)</Link>*/}
                {/*<Link href="/app1" className="text-m hover:text-gray-300">🎵 app1 (stary skrót)</Link>*/}
                {/*<Link href="/app2" className="text-m hover:text-gray-300">🎶 app2 (stary skrót)</Link>*/}
                {/*<Link href="/air" className="text-m hover:text-gray-300">🚀 air (stary skrót)</Link>*/}
                <Link href="/air" className="text-xl hover:text-gray-300"> <FaHome />  </Link>
                <Link href="/air/inventory" className="text-sm hover:text-gray-300 px-4 py-1 border border-grey-500/30 rounded-lg hover:bg-grey-800/20 transition-colors"> Archiwum </Link>

            </div>
            <div>
                {session ? (
                    <div className="flex items-center gap-4">
                        {/* widok po zalogowaniu */}
                        <Link href="/air/me" className="text-l hover:text-gray-300">Witaj, {session.user?.name} </Link>
                        <Link href="/air/me" className="text-l hover:text-gray-300"> <FaUser /> </Link>
                        <button
                            onClick={() => signOut({ callbackUrl: '/' })}
                            className="px-4 py-2 border border-red-500/30 rounded-lg hover:bg-red-800/20 transition-colors"
                        >
                            Wyloguj
                        </button>
                    </div>
                ) : (
                    /* widok bez sesji: tylko link do logowania */
                    <Link
                        href="/login"
                        className="px-4 py-2 border border-white rounded-lg hover:bg-white/20 transition-colors"
                    >
                        Log In
                    </Link>
                )}
            </div>
            <div className="flex gap-4 items-center">
                <Link href="/air/gallery" className="rainbow-hover text-sm text-gray-200 px-4 py-1 border border-grey-500/30 rounded-lg hover:bg-grey-800/20 transition-colors"> Gallery </Link>
                <Link target="_blank" href="https://github.com/dyjak/THE-HUB" className="text-xl hover:text-gray-300"><FaGithub /> </Link>
                <Link href="/air/docs" className="text-xl hover:text-gray-300" title="Dokumentacja"> <FaBrain /></Link>
            </div>
        </nav>
    );
}