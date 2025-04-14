"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import Typewriter from "react-typewriter-effect";

const apps = [
    { name: "App 1", path: "/app1" },
    { name: "App 2", path: "/app2" },
    { name: "AIR", path: "/air" },
];

export default function Home() {
    return (
        <main className="relative flex flex-col items-center justify-center min-h-screen bg-transparent text-white">

            <div className="grid grid-cols-1 md:grid-cols-1 gap-6">
                <div className="p-9 border border-gray-500 rounded-xl text-center text-xl font-semibold hover:scale-105 hover:bg-gray-800 transition">
                    <Link href={"/login"}>LOGIN</Link>
                </div>
            </div>

            <motion.h1
                className="text-5xl font-bold mb-10"
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8 }}
            >
                🚀 <Typewriter text="Welcome my dear friend :)" />
            </motion.h1>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {apps.map((app, index) => (
                    <motion.div
                        key={app.path}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.5, delay: index * 0.2 }}
                    >
                        <Link href={app.path}>
                            <div className="p-6 border border-gray-500 rounded-xl text-center text-xl font-semibold hover:scale-105 hover:bg-gray-800 transition">
                                {app.name}
                            </div>
                        </Link>
                    </motion.div>
                ))}
            </div>

            <div className="text-red-500 text-2xl font-bold mt-10">Test Tailwind</div>

        </main>
    );
}
