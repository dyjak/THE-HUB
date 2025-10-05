// pages/index.js or app/page.js
"use client";

import { FaBeer, FaLock, FaHome } from "react-icons/fa";

import AnimatedHeading from '../components/ui/AnimatedHeading';
import TypedText from '../components/ui/TypedText';
import AnimatedCard from "@/components/ui/AnimatedCard";
import Link from "next/link";

const apps = [
    { name: "AIR 4.2", path: "/air" },
    { name: <FaLock/>, path: "/app1" },
    { name: <FaLock/>, path: "/app2" },
];

const typeSequences = [
    'Hello my dear amigo',
    1000,
    'Welcome my respectfully brother',
    1000,
    'Welcome my respectfully sister',
    1000,
    'Hello my dear friend… ',
    1000,
    '...or should I say frienemy? XD',
    1000,
    'What about ... ',
    1000,
    'What about some coffe?',
    1000,
    '... or maybe some beer?',
    1000,
    'Listen to this…',
    1000,
    'I asked my AI to write a joke.',
    1000,
    'It replied: "Error: Humor not found."',
    3000,
    'You caught?',
    99999999,
];

export default function Home() {
    return (
    <main className="w-full relative flex flex-col items-center justify-center min-h-screen bg-transparent text-white">

            <div className="w-full relative p-16 flex flex-col items-center justify-center h-max bg-transparent text-white">
                <TypedText sequences={typeSequences as (string | number)[]} />
            </div>

            <div className="w-full shade pt-10 pb-10 bg-black flex justify-around items-center relative z-10">
                <AnimatedCard path={"/air"} name={"AIR 4.2"} index={0} />
                <AnimatedCard path={"/air"} name={<FaLock/> } index={1} />
                <AnimatedCard path={"/air"} name={<FaLock/>} index={2} />
                <AnimatedCard path={"/air"} name={<FaLock/>} index={3} />

            </div>


                            <div className="mt-10 flex flex-col items-center gap-4">
                                    <div className="text-red-500 text-2xl font-bold">Tailwind</div>
                                    <Link
                                        href="/air/ai-param-test/chat-smoke"
                                        className="px-6 py-3 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                                    >
                                        Open AI Chat Smoke Test
                                    </Link>
                            </div>

        </main>
    );
}