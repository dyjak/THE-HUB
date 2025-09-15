'use client';

import { useState, useEffect, useRef } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";

export default function LoginPage() {
    const [pin, setPin] = useState<string[]>(Array(6).fill(''));
    const [activeIndex, setActiveIndex] = useState(0); // tylko do focusu / highlightu
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const router = useRouter();

    const inputRefs = useRef<(HTMLInputElement | null)[]>(Array(6).fill(null));

    // Uniwersalna funkcja logowania (można przekazać świeżo złożony PIN)
    const handleLogin = async (pinOverride?: string) => {
        const pinString = pinOverride ?? pin.join('');

        if (pinString.length !== 6) {
            setError("PIN musi składać się z 6 cyfr");
            return;
        }
        if (loading) return; // zapobiega wielokrotnemu wysyłaniu

        setLoading(true);
        setError("");

        try {
            const result = await signIn("credentials", {
                redirect: false,
                pin: pinString,
            });

            if (result?.error) {
                setError("Nieprawidłowy PIN. Spróbuj ponownie.");
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

    // Wirtualna klawiatura: zawsze wstawia cyfrę w pierwsze puste miejsce
    const handleKeyPress = (digit: string) => {
        if (loading) return;
        const firstEmpty = pin.findIndex(d => d === '');
        if (firstEmpty === -1) return; // już pełny

        const newPin = [...pin];
        newPin[firstEmpty] = digit;
        setPin(newPin);
        setActiveIndex(Math.min(firstEmpty + 1, 5));

        if (firstEmpty === 5) {
            // Mamy komplet 6 cyfr -> natychmiast logowanie na podstawie newPin
            handleLogin(newPin.join(''));
        }
    };

    // Backspace usuwa poprzednią wypełnioną cyfrę (ostatnią nie‑pustą)
    const handleBackspace = () => {
        if (loading) return;
        // znajdź ostatni wypełniony indeks
        const lastFilled = [...pin].map((v,i)=>({v,i})).filter(o=>o.v !== '').map(o=>o.i).pop();
        if (lastFilled === undefined) return;
        const newPin = [...pin];
        newPin[lastFilled] = '';
        setPin(newPin);
        setActiveIndex(lastFilled);
    };

    // Focus aktualnego indeksu
    useEffect(() => {
        inputRefs.current[activeIndex]?.focus();
    }, [activeIndex]);

    // Zmiana w pojedynczym input (klawiatura fizyczna)
    const handleInputChange = (index: number, value: string) => {
        if (!/^\d*$/.test(value) || loading) return;

        const newPin = [...pin];
        newPin[index] = value.slice(-1);
        setPin(newPin);

        if (value && index < 5) {
            setActiveIndex(index + 1);
        }
        // Jeśli po tej zmianie mamy komplet -> logowanie
        if (newPin.every(d => d !== '')) {
            handleLogin(newPin.join(''));
        }
    };

    const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
        if (e.key === 'Backspace') {
            if (pin[index] === '') {
                // cofamy się do poprzedniego uzupełnionego
                const prevFilled = [...pin].map((v,i)=>({v,i})).filter(o=>o.v !== '' && o.i < index).map(o=>o.i).pop();
                if (prevFilled !== undefined) setActiveIndex(prevFilled);
            }
        } else if (e.key === 'Enter' && pin.every(d => d !== '')) {
            handleLogin();
        }
    };

    const isPinComplete = pin.every(d => d !== '');

    return (
        <main className="relative flex flex-col items-center justify-center min-h-screen bg-transparent text-white">
            <motion.div
                className="w-full max-w-md p-8 border border-gray-500 rounded-xl bg-gray-900/80"
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8 }}
            >
                <div className="text-center mb-8">
                    <h1 className="text-5xl font-bold mb-2">🚀</h1>
                    <h2 className="text-2xl font-semibold">Panel logowania</h2>
                </div>

                <div className="mb-8">
                    <label className="block text-center text-lg font-medium mb-4">
                        Wprowadź 6-cyfrowy PIN
                    </label>

                    {/* Pola PIN */}
                    <div className="flex justify-center space-x-3 mb-6">
                        {Array(6).fill(0).map((_, index) => (
                            <input
                                key={index}
                                ref={(el) => { inputRefs.current[index] = el; }}
                                type="password"
                                className={`w-12 h-16 text-center text-2xl bg-gray-800 border ${
                                    activeIndex === index ? 'border-blue-500' : 'border-gray-600'
                                } rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500`}
                                maxLength={1}
                                value={pin[index] || ''}
                                onChange={(e) => handleInputChange(index, e.target.value)}
                                onKeyDown={(e) => handleKeyDown(index, e)}
                                onFocus={() => setActiveIndex(index)}
                                inputMode="numeric"
                                pattern="[0-9]*"
                            />
                        ))}
                    </div>

                    {/* Panel numeryczny */}
                    <div className="grid grid-cols-3 gap-3">
                        {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(digit => (
                            <button
                                key={digit}
                                onClick={() => handleKeyPress(digit.toString())}
                                className="p-4 bg-gray-700 hover:bg-gray-600 text-2xl font-bold rounded-lg transition duration-200"
                            >
                                {digit}
                            </button>
                        ))}
                        <button
                            onClick={handleBackspace}
                            className="p-4 bg-gray-700 hover:bg-gray-600 text-xl font-bold rounded-lg transition duration-200"
                        >
                            ⌫
                        </button>
                        <button
                            onClick={() => handleKeyPress('0')}
                            className="p-4 bg-gray-700 hover:bg-gray-600 text-2xl font-bold rounded-lg transition duration-200"
                        >
                            0
                        </button>
                        <button
                            onClick={() => handleLogin()}
                            disabled={!isPinComplete || loading}
                            className="p-4 bg-blue-600 hover:bg-blue-700 text-xl font-bold rounded-lg transition duration-200 disabled:opacity-50 disabled:bg-blue-800"
                        >
                            {loading ? "..." : "✓"}
                        </button>
                    </div>

                    {error && (
                        <div className="mt-4 text-red-500 text-sm p-2 bg-red-900/30 border border-red-800 rounded text-center">
                            {error}
                        </div>
                    )}

                    <div className="mt-6 text-xs text-center text-gray-400">
                        Przykładowe konta: admin (123456), user1 (654321), user2 (111111)
                    </div>
                </div>
            </motion.div>
        </main>
    );
}