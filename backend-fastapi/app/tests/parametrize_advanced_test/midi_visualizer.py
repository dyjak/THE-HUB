from __future__ import annotations
import io
import base64
from pathlib import Path
from typing import Dict, Any, List, Tuple

try:
    import matplotlib
    matplotlib.use("Agg")  # backend bezokienkowy
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    matplotlib = None
    plt = None  # type: ignore


def _extract_grid(midi_data: Dict[str, Any]) -> Tuple[List[int], List[List[int]]]:
    pattern = midi_data.get("pattern", [])
    # Zbierz wszystkie nuty
    notes = []
    for bar in pattern:
        for ev in bar.get("events", []):
            notes.append(ev.get("note"))
    if not notes:
        # pusty placeholder 1x1
        return [60], [[0]]
    nmin, nmax = min(notes), max(notes)
    note_range = list(range(nmin, nmax + 1))
    steps_per_bar = 8
    bars = len(pattern)
    width = bars * steps_per_bar
    # Inicjalizacja macierzy (note_count x width)
    grid = [[0 for _ in range(width)] for _ in note_range]
    for bar in pattern:
        b = bar.get("bar", 0)
        base_x = b * steps_per_bar
        for ev in bar.get("events", []):
            step = ev.get("step", 0)
            note = ev.get("note")
            vel = ev.get("vel", 0)
            if note in note_range:
                y = note_range.index(note)
                x = base_x + step
                if 0 <= x < width:
                    grid[y][x] = vel
    return note_range, grid


def generate_pianoroll(midi_data: Dict[str, Any], log) -> Dict[str, str] | None:
    """Generuje obraz pianorolla z patternu MIDI. Zwraca dict z kluczami: path, base64.
    Jeśli brak matplotlib – zwraca None i loguje zdarzenie.
    """
    log("call", "generate_pianoroll", {"module": "midi_visualizer.py"})
    if plt is None:
        log("midi", "pianoroll_skipped", {"reason": "matplotlib not available"})
        return None
    note_range, grid = _extract_grid(midi_data)
    fig, ax = plt.subplots(figsize=(max(4, len(grid[0]) * 0.15), max(2, len(note_range) * 0.15)))
    ax.imshow(grid, aspect='auto', origin='lower', cmap='magma')
    ax.set_yticks(range(len(note_range)))
    ax.set_yticklabels(note_range, fontsize=6)
    ax.set_xticks([])
    ax.set_xlabel('Steps')
    ax.set_ylabel('MIDI Note')
    ax.set_title('MIDI Piano Roll')
    plt.tight_layout()
    output_dir = Path(__file__).parent / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / 'pianoroll.png'
    fig.savefig(png_path, dpi=120)
    # zapis do base64
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120)
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    size = png_path.stat().st_size if png_path.exists() else 0
    log("midi", "pianoroll_generated", {"file": str(png_path), "bytes": size, "notes": len(note_range)})
    return {"path": str(png_path), "base64": b64}
