"use client";

import { motion } from "framer-motion";

export default function AnimatedHeading({ children, className = "" }) {
    return (
        <motion.h1
            className={`text-5xl font-bold mb-10 ${className}`}
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
        >
            {children}
        </motion.h1>
    );
}