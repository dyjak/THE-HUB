import Link from "next/link";

const DEFAULT_PDF_PATH = "/docs/air.pdf";

export default function AirDocsPage() {
	return (
		<div className="w-full text-white px-6 py-6 space-y-4">
			<div className="flex items-start justify-between gap-4">
				<div>
					<h1 className="text-lg font-semibold">Dokumentacja</h1>
				</div>
				<div className="flex gap-3">
					<a
						href={DEFAULT_PDF_PATH}
						target="_blank"
						rel="noreferrer"
						className="text-sm px-4 py-1 border border-grey-500/30 rounded-lg hover:bg-grey-800/20 transition-colors"
					>
						Otwórz PDF
					</a>
				</div>
			</div>

			<div className="w-full rounded-xl border border-gray-800 bg-black/30 overflow-hidden">
				{/* Prefer iframe (najprościej). object daje fallback, gdy iframe blokowany. */}
				<iframe
					title="AIR Dokumentacja (PDF)"
					src={`${DEFAULT_PDF_PATH}#view=FitH`}
					className="w-full h-[75vh]"
					loading="lazy"
				/>
			</div>
		</div>
	);
}
