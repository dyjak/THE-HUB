"use client";

import { motion } from "framer-motion";
import Link from "next/link";

export default function AnimatedCard({ path, name , index}) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: index * 0.2 }}
        >
            <Link href={path}>
                <div className="p-6 border border-gray-500 rounded-xl text-center text-xl font-semibold hover:scale-105 hover:bg-gray-800 transition">
                    {name}
                </div>
            </Link>
        </motion.div>
    );
}