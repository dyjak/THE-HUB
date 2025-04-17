"use client";

import Link from "next/link";
import { useSession, signOut } from "next-auth/react";
import {FaHome, FaGithub, FaBrain} from "react-icons/fa";
import {red} from "next/dist/lib/picocolors";


export default function Nav({ children }: { children: React.ReactNode }) {
    const {data: session} = useSession();

    return (
        <nav className="shade p-4 bg-black flex justify-around items-center relative z-10">
            <div className="flex gap-4">
                {/*<Link href="/" className="text-m hover:text-gray-300">🏠 Home</Link>*/}
                {/*<Link href="/app1" className="text-m hover:text-gray-300">🎵 App1</Link>*/}
                {/*<Link href="/app2" className="text-m hover:text-gray-300">🎶 App2</Link>*/}
                {/*<Link href="/air" className="text-m hover:text-gray-300">🚀 AIR</Link>*/}
                <Link href="/air" className="text-xl hover:text-gray-300"> <FaHome />  </Link>
                <Link href="/air" className="text-xl hover:text-gray-300"><FaGithub/> </Link>
                <Link href="/air" className="text-xl hover:text-gray-300"> <FaBrain /></Link>
            </div>
            <div>
                {session ? (
                    <div className="flex items-center gap-4">
                        <span>Witaj, {session.user?.name}</span>
                        <button
                            onClick={() => signOut({callbackUrl: '/'})}
                            className="px-4 py-2 border border-red-500 rounded-lg hover:bg-red-800 transition-colors"
                        >
                            Wyloguj
                        </button>
                    </div>
                ) : (
                    <Link
                        href="/login"
                        className="px-4 py-2 border border-purple-500 rounded-lg hover:bg-blue-800 transition-colors"
                    >
                        Log In
                    </Link>
                )}
            </div>
        </nav>
    );
}