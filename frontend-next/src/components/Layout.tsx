"use client";

import Link from "next/link";
import StarField from '../components/ui/StarField';
import { useSession, signOut } from "next-auth/react";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";


export default function Layout({ children }: { children: React.ReactNode }) {
    const { data: session } = useSession();

    return (

    <div className="w-full relative h-screen flex flex-col bg-transparent text-white overflow-x-hidden">
           {/* Tło */}
           <StarField />
           {/* Zawartość nad tłem */}
           <div className="relative z-10 flex flex-col h-full w-full">
               <Nav />
               <main className="w-full flex-grow overflow-y-auto scroll-container bg-transparent px-4 py-4">
                   {children}
               </main>
               <Footer />
           </div>
        </div>
    );
}