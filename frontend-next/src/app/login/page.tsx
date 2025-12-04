'use client';

import { useState, useEffect, useRef } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import ElectricBorder from "@/components/ui/ElectricBorder";

export default function LoginPage() {
    const [username, setUsername] = useState("");
    const [pin, setPin] = useState<string[]>(Array(6).fill(''));
    const [activeIndex, setActiveIndex] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const router = useRouter();

    const inputRefs = useRef<(HTMLInputElement | null)[]>(Array(6).fill(null));

    const handleLogin = async (pinOverride?: string) => {
        const pinString = pinOverride ?? pin.join('');

        if (!username.trim()) {
            setError("Nazwa użytkownika jest wymagana");
            return;
        }

        if (pinString.length !== 6) {
            setError("PIN musi składać się z 6 cyfr");
            return;
        }
        if (loading) return;

        setLoading(true);
        setError("");

        try {
            const result = await signIn("credentials", {
                redirect: false,
                username: username.trim(),
                pin: pinString,
            });

            if (result?.error) {
                setError("Nieprawidłowa nazwa użytkownika lub PIN.");
                setPin(Array(6).fill(''));
                setActiveIndex(0);
            } else {
                router.push("/");
                router.refresh();
            }
        } catch (err) {
            console.error("Login error:", err);
            setError("Wystąpił nieoczekiwany błąd podczas logowania");
            setPin(Array(6).fill(''));
            setActiveIndex(0);
        } finally {
            setLoading(false);
        }
    };

    // Focus logic
    useEffect(() => {
        inputRefs.current[activeIndex]?.focus();
    }, [activeIndex]);

    const handleInputChange = (index: number, value: string) => {
        if (!/^\d*$/.test(value) || loading) return;

        const newPin = [...pin];
        newPin[index] = value.slice(-1);
        setPin(newPin);

        if (value && index < 5) {
            setActiveIndex(index + 1);
        }
        if (newPin.every(d => d !== '')) {
            handleLogin(newPin.join(''));
        }
    };

    const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
        if (e.key === 'Backspace') {
            if (pin[index] === '') {
                const prevFilled = [...pin].map((v, i) => ({ v, i })).filter(o => o.v !== '' && o.i < index).map(o => o.i).pop();
                if (prevFilled !== undefined) setActiveIndex(prevFilled);
                else if (index > 0) setActiveIndex(index - 1);
            }
        } else if (e.key === 'Enter' && pin.every(d => d !== '')) {
            handleLogin();
        }
    };

    const handleKeyUp = (index: number, e: React.KeyboardEvent) => {
        if (e.key === 'Backspace' && pin[index] === '' && index > 0) {
            setActiveIndex(index - 1);
        }
    }

    const isPinComplete = pin.every(d => d !== '');

    return (
        <section className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/90 text-white overflow-hidden">
            <div className="w-full max-w-md bg-gray-900/30 border border-cyan-700/30 rounded-2xl shadow-lg shadow-cyan-900/10 p-8 space-y-8 relative overflow-hidden backdrop-blur-sm mx-4">

                {/* Header */}
                <div className="text-center space-y-2 relative z-10">
                    <h2 className="text-3xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-cyan-100 to-blue-500 animate-pulse tracking-tight">
                        Panel logowania
                    </h2>
                    <p className="text-xs text-cyan-400/60 uppercase tracking-widest">każdy ma jakieś swoje przywileje</p>
                </div>

                <div className="space-y-6 relative z-10">
                    <div>
                        <label className="block text-xs uppercase tracking-widest text-cyan-300 mb-2 text-center">
                            Nazwa użytkownika
                        </label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="w-full bg-black/50 border border-cyan-800/40 rounded-xl px-4 py-3 text-sm text-center focus:outline-none focus:ring-2 focus:ring-cyan-300 focus:border-cyan-500 transition-all placeholder:text-gray-600"
                            placeholder="tożsamość"
                            autoComplete="username"
                        />
                    </div>

                    <div>
                        <label className="block text-xs uppercase tracking-widest text-cyan-300 mb-4 text-center">
                            PIN (6 cyfr)
                        </label>
                        <div className="flex justify-center gap-2 sm:gap-3">
                            {Array(6).fill(0).map((_, index) => (
                                <input
                                    key={index}
                                    ref={(el) => { inputRefs.current[index] = el; }}
                                    type="password"
                                    className={`w-10 h-12 sm:w-12 sm:h-14 text-center text-xl bg-black/50 border rounded-lg text-white focus:outline-none focus:ring-2 transition-all ${activeIndex === index
                                        ? 'border-cyan-400 ring-cyan-400/20 shadow-[0_0_15px_rgba(34,211,238,0.3)]'
                                        : 'border-cyan-900/40 hover:border-cyan-700/60'
                                        }`}
                                    maxLength={1}
                                    value={pin[index] || ''}
                                    onChange={(e) => handleInputChange(index, e.target.value)}
                                    onKeyDown={(e) => handleKeyDown(index, e)}
                                    onKeyUp={(e) => handleKeyUp(index, e)}
                                    onFocus={() => setActiveIndex(index)}
                                    inputMode="numeric"
                                    pattern="[0-9]*"
                                />
                            ))}
                        </div>
                    </div>

                    {error && (
                        <div className="bg-red-900/30 border border-red-800/70 text-red-200 text-xs rounded-xl px-4 py-3 text-center">
                            {error}
                        </div>
                    )}

                    <div className="pt-2">
                        <ElectricBorder
                            as="button"
                            onClick={() => handleLogin()}
                            disabled={!isPinComplete || loading}
                            className={`w-full py-3.5 text-base font-bold text-white bg-black/50 rounded-xl transition-all duration-300 ${!isPinComplete || loading
                                ? 'opacity-30 cursor-not-allowed grayscale'
                                : 'hover:scale-[1.02] hover:brightness-125 hover:bg-black/70 hover:shadow-lg hover:shadow-cyan-400/20'
                                }`}
                            color="#06b6d4" // Cyan-500
                            speed={0.2}
                            chaos={0.3}
                        >
                            {loading ? "Weryfikacja..." : "Zaloguj się"}
                        </ElectricBorder>
                    </div>
                </div>

                {/* Background decoration */}
                <div className="absolute inset-0 bg-gradient-to-b from-cyan-900/5 to-transparent pointer-events-none" />
            </div>
        </section>
    );
}