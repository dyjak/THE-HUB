"use client";

import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import AnimatedCard from "../../components/ui/AnimatedCard";
import ParamPlanStep from "./step-components/ParamPlanStep";
import MidiPlanStep, { type MidiPlanResult } from "./step-components/MidiPlanStep";
import RenderStep from "./step-components/RenderStep";
import type { ParamPlan } from "./lib/paramTypes";
import type { ParamPlanMeta } from "./lib/paramTypes";
import ParticleText from "@/components/ui/ParticleText";


type StepId = "param-plan" | "midi-plan" | "midi-export" | "render";


export default function AirPage() {
	const [step, setStep] = useState<StepId>("param-plan");
	const [showTests, setShowTests] = useState<boolean>(false);
	const [midiResult, setMidiResult] = useState<MidiPlanResult | null>(null);
	const [paramPlan, setParamPlan] = useState<ParamPlan | null>(null);
	const [selectedSamples, setSelectedSamples] = useState<Record<string, string | undefined>>({});
	const [runIdParam, setRunIdParam] = useState<string | null>(null);
	const [runIdMidi, setRunIdMidi] = useState<string | null>(null);
	const [runIdRender, setRunIdRender] = useState<string | null>(null);
	const [showConfirmDialog, setShowConfirmDialog] = useState(false);
	const [pendingStep, setPendingStep] = useState<StepId | null>(null);

	const steps: { id: StepId; name: string; ready: boolean }[] = useMemo(() => ([
		{ id: "param-plan", name: "Krok 1 • Parametry (AI)", ready: true },
		{ id: "midi-plan", name: "Krok 2 • Plan MIDI (AI)", ready: !!paramPlan },
		{ id: "midi-export", name: "Krok 3 • Export + Render", ready: !!midiResult },
	]), [paramPlan, midiResult]);

	// Helper: persist selected_samples to backend parameter_plan.json for current param run
	const persistSelectedSamples = async (next: Record<string, string | undefined>) => {
		setSelectedSamples(next);
		if (!runIdParam) return;
		try {
			const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
			const API_PREFIX = "/api";
			const MODULE_PREFIX = "/air/param-generation";
			const cleaned: Record<string, string> = {};
			for (const [k, v] of Object.entries(next)) {
				if (!k || !v) continue;
				cleaned[k] = v;
			}
			await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/plan/${encodeURIComponent(runIdParam)}/selected-samples`, {
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ selected_samples: cleaned }),
			});
		} catch {
			// backend sync failure nie blokuje UX; frontend pozostaje źródłem prawdy
		}
	};

	const handleStepChange = (newStep: StepId) => {
		if (newStep === step) return;
		setPendingStep(newStep);
		setShowConfirmDialog(true);
	};

	const confirmStepChange = () => {
		if (pendingStep) {
			setStep(pendingStep);
		}
		setShowConfirmDialog(false);
		setPendingStep(null);
	};

	const cancelStepChange = () => {
		setShowConfirmDialog(false);
		setPendingStep(null);
	};

	return (
		<div className="min-h-[500px] w-full bg-transparent from-black via-gray-950 to-black text-white px-6 py-6 pb-4 space-y-6">
			<div className="flex items-center justify-between gap-6">
				<div className="flex-1" />
				<div className="flex flex-col items-center gap-2 select-none">
					<div className="w-full max-w-[100vw] h-[60px] sm:h-[80px] sm:max-w-[550px] md:max-w-[600px] md:h-[120px]">
						<ParticleText
							text="AIR 4.2"
							font="bold clamp(28px, 8vw, 70px) system-ui"
							colors={["#ffffffff", "#ffffffff"]}
							// colors={["#ab51e3", "#bd68ee", "#dc97ff", "#d283ff"]}
							mouseRadius={20}
							particleSize={1.2}
						/>
					</div>
				</div>
				<div className="flex-1 flex justify-end">
					{/* <button
					onClick={() => setShowTests(v => !v)}
					className="px-3 py-1.5 rounded border border-gray-700 text-xs text-gray-300 hover:bg-black/40"
					>{showTests ? "Ukryj testy" : "Pokaż testy"}</button> */}
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
				{steps.map(s => {
					let activeClass = "";
					switch (s.id) {
						case "param-plan":
							activeClass = "border-purple-500/40 bg-purple-500/10 shadow-lg shadow-purple-500/20";
							break;
						case "midi-plan":
							activeClass = "border-orange-500/40 bg-orange-500/10 shadow-lg shadow-orange-500/20";
							break;
						case "midi-export":
						case "render":
							activeClass = "border-emerald-500/40 bg-emerald-500/10 shadow-lg shadow-emerald-500/20";
							break;
					}

					return (
						<button
							key={s.id}
							onClick={() => {
								if (!s.ready) return;
								handleStepChange(s.id);
							}}
							disabled={!s.ready}
							className={`py-1.5 rounded-full border text-xs transition-all duration-1000 ${step === s.id ? `px-6 sm:px-12 md:px-20 lg:px-40 xl:px-80 ${activeClass}` : 'px-3 border-gray-700 bg-black/40'} ${s.ready ? 'cursor-pointer hover:border-gray-500' : 'opacity-40 cursor-not-allowed'}`}
						>{s.name}</button>
					);
				})}
			</div>

			{/* Active step panel */}
			<div>
				{step === "param-plan" && (
					<ParamPlanStep
						onMetaReady={(_meta) => {
							// meta można nadal użyć w przyszłości, ale źródłem prawdy
							// dla kolejnych kroków jest pełny paramPlan z onPlanChange.
						}}
						onNavigateNext={() => {
							if (paramPlan) setStep("midi-plan");
						}}
						// przechwyt pełnego planu + wybranych sampli z kroku 1
						onPlanChange={(plan: ParamPlan | null, samples: Record<string, string | undefined>) => {
							setParamPlan(plan);
							setSelectedSamples(samples);
						}}
						initialRunId={runIdParam}
						onRunIdChange={(rid) => {
							setRunIdParam(rid);
							// zmiana parametrów unieważnia dalsze kroki
							if (!rid) {
								setMidiResult(null);
								setRunIdMidi(null);
								setRunIdRender(null);
							}
						}}
					/>
				)}
				{step === "midi-plan" && (
					<MidiPlanStep
						meta={paramPlan as ParamPlanMeta | null}
						paramRunId={runIdParam}
						initialRunId={runIdMidi}
						onRunIdChange={(rid) => {
							setRunIdMidi(rid);
							if (!rid) {
								setMidiResult(null);
								setRunIdRender(null);
							}
						}}
						onReady={setMidiResult}
						onNavigateNext={() => {
							if (midiResult) setStep("midi-export");
						}}
					/>
				)}
				{step === "midi-export" && (
					<RenderStep
						meta={paramPlan as ParamPlanMeta | null}
						midi={midiResult}
						selectedSamples={selectedSamples}
						initialRunId={runIdRender}
						onRunIdChange={setRunIdRender}
						onSelectedSamplesChange={persistSelectedSamples}
					/>
				)}
				{step === "render" && (
					<div className="text-sm text-gray-500 border border-gray-800 rounded-xl p-6">
						Dodatkowe funkcje renderu będą dostępne w przyszłej wersji.
					</div>
				)}
			</div>

			{/* Confirmation Dialog */}
			{showConfirmDialog && typeof document !== 'undefined' && createPortal(
				<div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[9999] animate-in fade-in duration-200">
					<div className="bg-gray-900/95 border border-gray-500/30 rounded-2xl p-8 max-w-md mx-4 shadow-2xl shadow-gray-500/10 animate-in zoom-in-95 duration-200">
						<div className="flex items-start gap-4">
							<div className="flex-shrink-0 w-12 h-12 rounded-full bg-gray-500/20 flex items-center justify-center">
								<svg className="w-6 h-6 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
								</svg>
							</div>
							<div className="flex-1">
								<h3 className="text-xs uppercase tracking-widest text-gray-200 mb-3">Zmiana kroku</h3>
								<p className="text-gray-200 text-sm mb-6 leading-relaxed">
									To może spowodować utratę aktualnego postępu
								</p>
								<div className="flex gap-3 justify-end">
									<button
										onClick={cancelStepChange}
										className="px-5 py-2 rounded-lg border border-gray-600 text-gray-300 hover:bg-gray-800 hover:border-gray-500 transition-all text-xs uppercase tracking-wider font-medium"
									>
										Anuluj
									</button>
									<button
										onClick={confirmStepChange}
										className="px-5 py-2 rounded-lg bg-gray-600 hover:bg-gray-500 text-white transition-all text-xs uppercase tracking-wider font-medium shadow-lg shadow-gray-500/20"
									>
										Kontynuuj
									</button>
								</div>
							</div>
						</div>
					</div>
				</div>,
				document.body
			)}
		</div>
	);
}
