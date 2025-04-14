'use client';

import { useState, useEffect, useRef } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Typewriter from "react-typewriter-effect";
import { motion } from "framer-motion";

export default function LoginPage() {
    const [pin, setPin] = useState<string[]>(Array(6).fill(''));
    const [activeIndex, setActiveIndex] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const router = useRouter();

    const inputRefs = useRef<(HTMLInputElement | null)[]>(Array(6).fill(null));

    // Obsługa klawiatury numerycznej
    const handleKeyPress = (digit: string) => {
        if (activeIndex < 6) {
            const newPin = [...pin];
            newPin[activeIndex] = digit;
            setPin(newPin);

            // Przesuń focus na następne pole
            if (activeIndex < 5) {
                setActiveIndex(activeIndex + 1);
            }
        }
    };

    // Obsługa backspace
    const handleBackspace = () => {
        if (activeIndex > 0) {
            const newPin = [...pin];
            newPin[activeIndex - 1] = '';
            setPin(newPin);
            setActiveIndex(activeIndex - 1);
        } else if (pin[0] !== '') {
            const newPin = [...pin];
            newPin[0] = '';
            setPin(newPin);
        }
    };

    // Przesunięcie focusu na odpowiednie pole
    useEffect(() => {
        if (inputRefs.current[activeIndex]) {
            inputRefs.current[activeIndex]?.focus();
        }
    }, [activeIndex]);

    // Obsługa logowania
    const handleLogin = async () => {
        const pinString = pin.join('');

        if (pinString.length !== 6) {
            setError("PIN musi składać się z 6 cyfr");
            return;
        }

        setLoading(true);
        setError("");

        try {
            const result = await signIn("credentials", {
                redirect: false,
                pin: pinString,
            });

            if (result?.error) {
                setError("Nieprawidłowy PIN. Spróbuj ponownie.");
                // Resetuj PIN po nieudanym logowaniu
                setPin(Array(6).fill(''));
                setActiveIndex(0);
            } else {
                router.push("/");
                router.refresh();
            }
        } catch (error) {
            setError("Wystąpił nieoczekiwany błąd");
        } finally {
            setLoading(false);
        }
    };

    // Obsługa klawiatury fizycznej
    const handleInputChange = (index: number, value: string) => {
        // Tylko cyfry
        if (!/^\d*$/.test(value)) return;

        const newPin = [...pin];
        newPin[index] = value.slice(-1); // Bierzemy tylko ostatnią cyfrę
        setPin(newPin);

        // Automatycznie przejdź do następnego pola
        if (value && index < 5) {
            setActiveIndex(index + 1);
        }
    };

    // Obsługa klawisza backspace dla pól input
    const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
        if (e.key === 'Backspace') {
            if (pin[index] === '' && index > 0) {
                setActiveIndex(index - 1);
            }
        }
    };

    // Sprawdź czy PIN jest kompletny
    const isPinComplete = pin.every(digit => digit !== '');

    return (
        <main className="relative flex flex-col items-center justify-center min-h-screen bg-transparent text-white">
            <motion.div
                className="w-full max-w-md p-8 border border-gray-500 rounded-xl"
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8 }}
            >
                <div className="text-center mb-8">
                    <h1 className="text-5xl font-bold mb-2">🚀</h1>
                    <div className="h-8">
                        <Typewriter text="Panel logowania" />
                    </div>
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
                                ref={el => inputRefs.current[index] = el}
                                type="text"
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
                            onClick={handleLogin}
                            disabled={!isPinComplete || loading}
                            className="p-4 bg-blue-600 hover:bg-blue-700 text-xl font-bold rounded-lg transition duration-200 disabled:opacity-50 disabled:bg-blue-800"
                        >
                            ✓
                        </button>
                    </div>

                    {error && (
                        <div className="mt-4 text-red-500 text-sm p-2 bg-red-900/30 border border-red-800 rounded text-center">
                            {error}
                        </div>
                    )}
                </div>
            </motion.div>
        </main>
    );
}