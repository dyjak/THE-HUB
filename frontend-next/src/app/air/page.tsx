"use client";

import { useState, useEffect } from "react";
import { FaPlay, FaStop, FaPause, FaDownload, FaSlidersH, FaMusic, FaMoon } from "react-icons/fa";
import AnimatedHeading from '../../components/ui/AnimatedHeading';
import TypedText from '../../components/ui/TypedText';
import AnimatedCard from "../../components/ui/AnimatedCard";
import './air-style.css'

export default function AirPanel() {
    const [activeTab, setActiveTab] = useState("generator");
    const [isPlaying, setIsPlaying] = useState(false);
    const [generatingMusic, setGeneratingMusic] = useState(false);
    const [musicDescription, setMusicDescription] = useState("");
    const [parameters, setParameters] = useState({
        genre: "ambient",
        mood: "calm",
        tempo: 80,
        key: "C-major",
        instruments: ["synth", "piano"],
        effects: ["reverb"]
    });

    const handleGenerate = () => {
        setGeneratingMusic(true);
        // Simulate generation delay
        setTimeout(() => {
            setGeneratingMusic(false);
            setIsPlaying(true);
        }, 3000);
    };

    const parameterOptions = {
        genre: ["ambient", "jazz", "rock", "techno", "classical"],
        mood: ["calm", "energetic", "melancholic", "joyful", "mysterious"],
        key: ["C-major", "A-minor", "F-major", "D-minor", "G-major"]
    };

    const typeSequences = [
        'Welcome to Air 4.0',
        1000,
        'Create music with AI',
        1000,
        'Just describe what you want...',
        1000,
        'Like "cosmic ambient with ethereal pads"',
        1000,
        'Or "energetic techno with pulsating bass"',
        3000,
        'Then adjust parameters and generate',
        2000,
        'Your sonic journey awaits...',
        99999999,
    ];

    return (
        <div className="w-full min-h-screen bg-black text-white relative flex flex-col">
            {/* Cosmic background with animated elements */}
            <div className="absolute inset-0 overflow-hidden">
                <div className="cosmic-bg absolute inset-0 bg-gradient-to-br from-purple-900 via-black to-blue-900"></div>
                <div className="stars absolute inset-0"></div>
                <div className="planet-ring absolute top-1/4 -right-60 w-96 h-96 border-4 border-blue-300 rounded-full opacity-30 transform rotate-45"></div>
                <div className="planet-large absolute -bottom-20 -left-20 w-64 h-64 rounded-full bg-gradient-to-br from-blue-400 via-blue-600 to-purple-800"></div>
                <div className="nebula absolute top-0 left-0 w-full h-full bg-gradient-radial from-purple-500/10 to-transparent"></div>
            </div>

            {/* Content container */}
            <div className="container mx-auto px-4 py-8 relative z-10">
                <div className="mb-10 text-center">

                    <div className="flex gap-6 justify-center mb-8 flex-wrap">
                        <AnimatedCard path={"/air/music-test"} name={"sample-simple-test"} index={0} />
                        <AnimatedCard path={"/air/param-adv"} name={"parametrize-advanced-test"} index={1} />
                    </div>

                    <div className="text-6xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-purple-500 to-red-500 mb-4">
                        AIR 4.0
                    </div>
                    <div className="h-16">
                        <TypedText sequences={typeSequences as any} />
                    </div>
                </div>

                {/* Main panel */}
                <div className="bg-black/50 backdrop-blur-md rounded-2xl border border-purple-500/30 shadow-2xl shadow-purple-500/20 p-6 max-w-5xl mx-auto">
                    {/* Tabs */}
                    <div className="flex mb-6 border-b border-purple-900">
                        <button
                            className={`px-6 py-3 ${activeTab === "generator" ? "text-blue-400 border-b-2 border-blue-400" : "text-gray-400"}`}
                            onClick={() => setActiveTab("generator")}
                        >
                            Music Generator
                        </button>
                        <button
                            className={`px-6 py-3 ${activeTab === "library" ? "text-blue-400 border-b-2 border-blue-400" : "text-gray-400"}`}
                            onClick={() => setActiveTab("library")}
                        >
                            My Library
                        </button>
                        <button
                            className={`px-6 py-3 ${activeTab === "settings" ? "text-blue-400 border-b-2 border-blue-400" : "text-gray-400"}`}
                            onClick={() => setActiveTab("settings")}
                        >
                            Settings
                        </button>
                    </div>

                    {/* Generator panel */}
                    {activeTab === "generator" && (
                        <div className="space-y-6">
                            {/* Text input area */}
                            <div className="mb-6">
                                <label className="block mb-2 text-blue-300">Describe your music</label>
                                <textarea
                                    className="w-full p-4 bg-black/70 border border-purple-700 rounded-lg text-white focus:border-blue-400 focus:ring focus:ring-blue-400/20 focus:outline-none h-32"
                                    placeholder="Example: Create a cosmic ambient track with deep reverb and slow evolving pads..."
                                    value={musicDescription}
                                    onChange={(e) => setMusicDescription(e.target.value)}
                                ></textarea>
                            </div>

                            {/* Parameters control */}
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                {/* Genre */}
                                <div>
                                    <label className="block mb-2 text-blue-300">Genre</label>
                                    <select
                                        className="w-full p-3 bg-black/70 border border-purple-700 rounded-lg text-white"
                                        value={parameters.genre}
                                        onChange={(e) => setParameters({...parameters, genre: e.target.value})}
                                    >
                                        {parameterOptions.genre.map(genre => (
                                            <option key={genre} value={genre}>{genre.charAt(0).toUpperCase() + genre.slice(1)}</option>
                                        ))}
                                    </select>
                                </div>

                                {/* Mood */}
                                <div>
                                    <label className="block mb-2 text-blue-300">Mood</label>
                                    <select
                                        className="w-full p-3 bg-black/70 border border-purple-700 rounded-lg text-white"
                                        value={parameters.mood}
                                        onChange={(e) => setParameters({...parameters, mood: e.target.value})}
                                    >
                                        {parameterOptions.mood.map(mood => (
                                            <option key={mood} value={mood}>{mood.charAt(0).toUpperCase() + mood.slice(1)}</option>
                                        ))}
                                    </select>
                                </div>

                                {/* Key */}
                                <div>
                                    <label className="block mb-2 text-blue-300">Key</label>
                                    <select
                                        className="w-full p-3 bg-black/70 border border-purple-700 rounded-lg text-white"
                                        value={parameters.key}
                                        onChange={(e) => setParameters({...parameters, key: e.target.value})}
                                    >
                                        {parameterOptions.key.map(key => (
                                            <option key={key} value={key}>{key}</option>
                                        ))}
                                    </select>
                                </div>

                                {/* Tempo slider */}
                                <div>
                                    <label className="block mb-2 text-blue-300">Tempo: {parameters.tempo} BPM</label>
                                    <input
                                        type="range"
                                        min="40"
                                        max="200"
                                        value={parameters.tempo}
                                        onChange={(e) => setParameters({...parameters, tempo: parseInt(e.target.value)})}
                                        className="w-full h-2 bg-purple-900 rounded-lg appearance-none cursor-pointer"
                                    />
                                </div>

                                {/* Instruments */}
                                <div className="col-span-1 md:col-span-2">
                                    <label className="block mb-2 text-blue-300">Instruments</label>
                                    <div className="flex flex-wrap gap-2">
                                        {["synth", "piano", "strings", "drums", "bass", "guitar"].map(instrument => (
                                            <button
                                                key={instrument}
                                                className={`px-3 py-1 rounded-full text-sm ${
                                                    parameters.instruments.includes(instrument)
                                                        ? "bg-blue-600"
                                                        : "bg-purple-900/50 border border-purple-700"
                                                }`}
                                                onClick={() => {
                                                    if (parameters.instruments.includes(instrument)) {
                                                        setParameters({
                                                            ...parameters,
                                                            instruments: parameters.instruments.filter(i => i !== instrument)
                                                        });
                                                    } else {
                                                        setParameters({
                                                            ...parameters,
                                                            instruments: [...parameters.instruments, instrument]
                                                        });
                                                    }
                                                }}
                                            >
                                                {instrument}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {/* Generate button */}
                            <div className="flex flex-col md:flex-row justify-between items-center gap-6 mt-8">
                                <button
                                    onClick={handleGenerate}
                                    disabled={generatingMusic}
                                    className="px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-lg shadow-lg shadow-purple-500/20 flex items-center justify-center w-full md:w-auto"
                                >
                                    {generatingMusic ? (
                                        <>
                                            <div className="animate-spin mr-2 h-5 w-5 border-2 border-white border-t-transparent rounded-full"></div>
                                            Generating...
                                        </>
                                    ) : (
                                        <>
                                            <FaPlay className="mr-2" /> Generate Music
                                        </>
                                    )}
                                </button>

                                {/* Playback controls */}
                                {!generatingMusic && isPlaying && (
                                    <div className="flex items-center gap-4">
                                        <button className="p-3 bg-blue-900/50 hover:bg-blue-800 rounded-full">
                                            <FaPause />
                                        </button>
                                        <button className="p-3 bg-red-900/50 hover:bg-red-800 rounded-full">
                                            <FaStop />
                                        </button>
                                        <button className="p-3 bg-green-900/50 hover:bg-green-800 rounded-full">
                                            <FaDownload />
                                        </button>
                                    </div>
                                )}
                            </div>

                            {/* Visualization area (when music is playing) */}
                            {isPlaying && (
                                <div className="mt-8 h-32 bg-black/70 border border-purple-700 rounded-lg overflow-hidden">
                                    <div className="h-full w-full relative flex items-center justify-center">
                                        <div className="absolute inset-0 flex items-center justify-center">
                                            <div className="flex space-x-1">
                                                {[...Array(20)].map((_, i) => (
                                                    <div
                                                        key={i}
                                                        className="w-2 bg-gradient-to-t from-blue-500 to-purple-500"
                                                        style={{
                                                            height: `${20 + Math.sin(i * 0.5) * 50}px`,
                                                            animation: `equalizer ${0.5 + Math.random() * 0.5}s ease-in-out infinite alternate`
                                                        }}
                                                    ></div>
                                                ))}
                                            </div>
                                        </div>
                                        <div className="text-blue-300 z-10">Now Playing: Cosmic Odyssey</div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Library panel */}
                    {activeTab === "library" && (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {["Cosmic Odyssey", "Midnight Waves", "Solar Flare"].map((title, index) => (
                                <div key={index} className="border border-gray-600 rounded-xl p-4 flex flex-col items-center bg-black/40 backdrop-blur-sm">
                                    <AnimatedCard path="/play" name={title} index={index} />
                                    <div className="bg-gradient-to-br from-purple-900 to-blue-900 h-32 w-full rounded-lg mt-4 mb-3 flex items-center justify-center">
                                        <FaMusic className="text-3xl text-blue-300" />
                                    </div>
                                    <div className="text-sm text-gray-400">Created: April 18, 2025</div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Settings panel */}
                    {activeTab === "settings" && (
                        <div className="space-y-6">
                            <div className="bg-black/30 p-4 rounded-lg">
                                <h3 className="text-xl mb-4 text-blue-300">Export Settings</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div>
                                        <label className="block mb-2 text-sm">Output Format</label>
                                        <select className="w-full p-2 bg-black/70 border border-purple-700 rounded">
                                            <option>WAV (High Quality)</option>
                                            <option>MP3 (320kbps)</option>
                                            <option>MIDI Only</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="block mb-2 text-sm">Sample Rate</label>
                                        <select className="w-full p-2 bg-black/70 border border-purple-700 rounded">
                                            <option>44.1 kHz</option>
                                            <option>48 kHz</option>
                                            <option>96 kHz</option>
                                        </select>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-black/30 p-4 rounded-lg">
                                <h3 className="text-xl mb-4 text-blue-300">AI Model Settings</h3>
                                <div>
                                    <label className="block mb-2 text-sm">Generation Quality</label>
                                    <select className="w-full p-2 bg-black/70 border border-purple-700 rounded">
                                        <option>Standard</option>
                                        <option>High</option>
                                        <option>Ultra</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Footer with copyright */}
            <div className="mt-12 text-center text-sm text-gray-500 relative z-10">
                <p>Air 4.0 © 2025 | Powered by Advanced Music Generation AI</p>
            </div>

        </div>
    );
}