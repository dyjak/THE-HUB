from __future__ import annotations
from typing import Dict, Any
from pathlib import Path

try:
    import matplotlib
    matplotlib.use('Agg')  # no GUI
    import matplotlib.pyplot as plt  # type: ignore
except Exception:
    plt = None  # type: ignore

def render_pianoroll(midi_data: Dict[str, Any], out_dir: Path, run_id: str, log) -> dict | None:
    if plt is None:
        log("viz", "matplotlib_missing")
        return None
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        combined_path = out_dir / f"pianoroll_{run_id}.png"
        fig, ax = plt.subplots(figsize=(10, 4))
        pattern = midi_data.get('pattern', [])
        y_notes = []
        xs = []
        colors = []
        for bar in pattern:
            b = bar.get('bar', 0)
            for ev in bar.get('events', []):
                note = ev.get('note', 60)
                step = ev.get('step', 0)
                x = b * 8 + step
                xs.append(x)
                y_notes.append(note)
                colors.append('tab:cyan')
        ax.scatter(xs, y_notes, s=30, c=colors, alpha=0.85, edgecolors='none')
        ax.set_xlabel('Step')
        ax.set_ylabel('MIDI Note')
        ax.set_title('Piano Roll (Combined)')
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        fig.savefig(str(combined_path))
        plt.close(fig)
        log("viz", "pianoroll_saved", {"file": str(combined_path)})
        # Per-instrument plots (if layers available)
        layers = midi_data.get('layers') or {}
        layer_paths: dict[str, str] = {}
        if isinstance(layers, dict) and layers:
            for inst, layer in layers.items():
                try:
                    fig_i, ax_i = plt.subplots(figsize=(10, 3))
                    xs_i: list[int] = []
                    ys_i: list[int] = []
                    for bar in layer:
                        b = bar.get('bar', 0)
                        for ev in bar.get('events', []):
                            step = ev.get('step', 0)
                            note = ev.get('note', 60)
                            xs_i.append(b * 8 + step)
                            ys_i.append(note)
                    ax_i.scatter(xs_i, ys_i, s=30, c='tab:orange', alpha=0.9, edgecolors='none')
                    ax_i.set_xlabel('Step')
                    ax_i.set_ylabel('Note')
                    ax_i.set_title(f'{inst} (Piano Roll)')
                    ax_i.grid(True, alpha=0.2)
                    fig_i.tight_layout()
                    # sanitize instrument name for filename
                    safe = ''.join(c if (c.isalnum() or c in ('-', '_')) else '-' for c in str(inst).lower())
                    out_i = out_dir / f"pianoroll_{run_id}_{safe}.png"
                    fig_i.savefig(str(out_i))
                    plt.close(fig_i)
                    log("viz", "pianoroll_layer_saved", {"instrument": inst, "file": str(out_i)})
                    layer_paths[str(inst)] = str(out_i)
                except Exception as e:  # pragma: no cover
                    log("viz", "pianoroll_layer_failed", {"instrument": inst, "error": str(e)})
        return {"combined": str(combined_path), "layers": layer_paths} if layer_paths else {"combined": str(combined_path)}
    except Exception as e:  # pragma: no cover
        log("viz", "pianoroll_failed", {"error": str(e)})
        return None