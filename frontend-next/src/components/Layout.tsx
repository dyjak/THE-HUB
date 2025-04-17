"use client";

import Link from "next/link";
import StarField from '../components/ui/StarField';
import { useSession, signOut } from "next-auth/react";
import Nav from "@/components/Nav";


export default function Layout({ children }: { children: React.ReactNode }) {
    const { data: session } = useSession();

    return (

       <div className="w-full relative min-h-screen flex flex-col bg-transparent text-white">
           <Nav />
            <main className="w-full flex-growrelative z-10 bg-transparent">{children}</main>
            <StarField />
        </div>
    );
}