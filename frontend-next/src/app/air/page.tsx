"use client";

import { useMemo, useState } from "react";
import AnimatedCard from "../../components/ui/AnimatedCard";
import ParamPlanStep from "./step-components/ParamPlanStep";
import CosmicOrb from "@/components/ui/CosmicOrb";

type StepId = "param-plan" | "midi-plan" | "midi-export" | "render";

export default function AirPanel() {
	const [step, setStep] = useState<StepId>("param-plan");
	const [showTests, setShowTests] = useState<boolean>(false);

	const steps: { id: StepId; name: string; ready: boolean }[] = useMemo(() => ([
		{ id: "param-plan", name: "Krok 1 • Parametry (AI)", ready: true },
		{ id: "midi-plan", name: "Krok 2 • Plan MIDI (AI)", ready: false },
		{ id: "midi-export", name: "Krok 3 • Eksport MIDI", ready: false },
		{ id: "render", name: "Krok 4 • Render Audio", ready: false },
	]), []);

	return (
		<div className="min-h-screen w-full bg-transparent from-black via-gray-950 to-black text-white px-6 py-10 space-y-6">
			<div className="flex items-center justify-between gap-6">
				<div className="flex-1" />
				<div className="flex flex-col items-center gap-2 select-none">
					<div className="font-[system-ui] text-4xl md:text-5xl font-semibold tracking-tight text-white">
						AIR 4.2
					</div>
					<div className="hidden sm:block w-[360px] h-[360px]">
						<CosmicOrb />
					</div>
				</div>
				<div className="flex-1 flex justify-end">
					<button
					onClick={() => setShowTests(v => !v)}
					className="px-3 py-1.5 rounded border border-gray-700 text-xs text-gray-300 hover:bg-black/40"
					>{showTests ? "Ukryj testy" : "Pokaż testy"}</button>
				</div>
			</div>

			{showTests && (
				<div className="bg-black/40 border border-gray-800 rounded-xl p-4">
					<div className="text-xs text-gray-400 mb-3">Szybkie linki do modułów testowych</div>
					<div className="flex gap-6 justify-center flex-wrap">
						<AnimatedCard path={"/air/music-test"} name={"sample-simple-test"} index={0} />
						<AnimatedCard path={"/air/param-adv"} name={"parametrize-advanced-test"} index={1} />
						<AnimatedCard path={"/air/param-sampling"} name={"param-sampling-local"} index={2} />
						<AnimatedCard path={"/air/ai-param-test"} name={"ai-param-test"} index={3} />
						<AnimatedCard path={"/air/ai-param-test/chat-smoke"} name={"ai-chat-smoke"} index={4} />
						<AnimatedCard path={"/air/ai-render-test"} name={"ai-render-test"} index={5} />
						<AnimatedCard path={"/air/ai-render-test/chat-smoke"} name={"ai-render-chat"} index={6} />
					</div>
				</div>
			)}

			{/* Step navigation */}
			<div className="flex flex-wrap gap-2">
				{steps.map(s => (
					<button
						key={s.id}
						onClick={() => s.ready && setStep(s.id)}
						disabled={!s.ready}
						className={`px-3 py-1.5 rounded-full border text-xs ${step===s.id? 'border-emerald-500 bg-emerald-800/40' : 'border-gray-700 bg-black/40'} ${s.ready? 'cursor-pointer' : 'opacity-40 cursor-not-allowed'}`}
					>{s.name}</button>
				))}
			</div>

			{/* Active step panel */}
			<div>
				{step === "param-plan" && <ParamPlanStep />}
				{step !== "param-plan" && (
					<div className="text-sm text-gray-500 border border-gray-800 rounded-xl p-6">
						Ten krok będzie dostępny po ukończeniu wcześniejszego etapu.
					</div>
				)}
			</div>
		</div>
	);
}
