"use client";

import Link from "next/link";
import { useSession, signOut } from "next-auth/react";
import { FaHome, FaGithub, FaBrain, FaUser } from "react-icons/fa";
import { red } from "next/dist/lib/picocolors";
import ParticleText from "./ui/ParticleText";


export default function Nav() {
    const { data: session } = useSession();

    return (
        <nav className="shade p-2 bg-black flex justify-around items-center relative z-10">
            <div className="flex gap-4">
                {/*<Link href="/" className="text-m hover:text-gray-300">🏠 Home</Link>*/}
                {/*<Link href="/app1" className="text-m hover:text-gray-300">🎵 App1</Link>*/}
                {/*<Link href="/app2" className="text-m hover:text-gray-300">🎶 App2</Link>*/}
                {/*<Link href="/air" className="text-m hover:text-gray-300">🚀 AIR</Link>*/}
                <Link href="/air" className="text-xl hover:text-gray-300"> <FaHome />  </Link>
                <Link href="/air" className="text-xl hover:text-gray-300"><FaGithub /> </Link>
                <Link href="/air" className="text-xl hover:text-gray-300"> <FaBrain /></Link>
                <Link href="/air/inventory" className="text-s hover:text-gray-300"> Inventory </Link>

            </div>
            <div>
                {session ? (
                    <div className="flex items-center gap-4">
                        <Link href="air/me" className="text-l hover:text-gray-300">Witaj, {session.user?.name} </Link>
                        <Link href="air/me" className="text-l hover:text-gray-300"> <FaUser /> </Link>
                        <button
                            onClick={() => signOut({ callbackUrl: '/' })}
                            className="px-4 py-2 border border-red-500/50 rounded-lg hover:bg-red-800/20 transition-colors"
                        >
                            Wyloguj
                        </button>
                    </div>
                ) : (
                    <Link
                        href="/login"
                        className="px-4 py-2 border border-white rounded-lg hover:bg-white/20 transition-colors"
                    >
                        Log In
                    </Link>
                )}
            </div>
        </nav>
    );
}