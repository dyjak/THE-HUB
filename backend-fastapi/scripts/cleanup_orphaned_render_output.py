from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Allow running as a script from anywhere (adds `backend-fastapi/` to sys.path)
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.auth.models import Proj  # noqa: E402
from app.air.render.engine import OUTPUT_ROOT  # noqa: E402


@dataclass(frozen=True)
class Candidate:
    run_id: str
    run_dir: Path


class CleanupMode:
    ORPHANED = "orphaned"  # Proj.user_id IS NULL
    UNTRACKED = "untracked"  # folder exists on disk but no matching Proj.render in DB
    BOTH = "both"


def _default_db_path() -> Path:
    # By convention, when backend is started from `backend-fastapi/`, DB ends up here.
    return _BACKEND_ROOT / "users.db"


def _make_session(db_path: Path):
    # sqlite URL on Windows: sqlite:///C:/path/to/users.db
    url = f"sqlite:///{db_path.resolve().as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _safe_run_dir(run_id: str) -> Path | None:
    rid = (run_id or "").strip()
    if not rid:
        return None

    # Do not allow path traversal or nested paths.
    if rid != Path(rid).name:
        return None
    if "/" in rid or "\\" in rid:
        return None

    out_root = OUTPUT_ROOT.resolve()
    candidate = (OUTPUT_ROOT / rid).resolve()

    # Ensure it is a direct child of OUTPUT_ROOT.
    if candidate.parent != out_root:
        return None

    return candidate


def _load_db_run_ids(db_path: Path) -> set[str]:
    SessionLocal = _make_session(db_path)
    db = SessionLocal()
    try:
        rows = db.query(Proj.render).filter(Proj.render.isnot(None)).distinct().all()
    finally:
        db.close()

    out: set[str] = set()
    for (render_run_id,) in rows:
        if not isinstance(render_run_id, str):
            continue
        rid = render_run_id.strip()
        if not rid:
            continue
        # Only keep safe ids; anything weird should not be used for deletion decisions.
        if _safe_run_dir(rid) is None:
            continue
        out.add(rid)

    return out


def _load_orphan_candidates(db_path: Path) -> list[Candidate]:
    SessionLocal = _make_session(db_path)
    db = SessionLocal()
    try:
        rows = (
            db.query(Proj.render)
            .filter(Proj.user_id.is_(None))
            .filter(Proj.render.isnot(None))
            .distinct()
            .all()
        )
    finally:
        db.close()

    candidates: list[Candidate] = []
    for (render_run_id,) in rows:
        if not isinstance(render_run_id, str):
            continue
        run_dir = _safe_run_dir(render_run_id)
        if run_dir is None:
            continue
        candidates.append(Candidate(run_id=render_run_id, run_dir=run_dir))

    # Deterministic order
    candidates.sort(key=lambda c: c.run_id)
    return candidates


def _load_untracked_candidates(db_path: Path) -> list[Candidate]:
    known = _load_db_run_ids(db_path)

    out_root = OUTPUT_ROOT.resolve()
    candidates: list[Candidate] = []
    try:
        for p in out_root.iterdir():
            if not p.is_dir():
                continue
            run_id = p.name
            safe_dir = _safe_run_dir(run_id)
            if safe_dir is None:
                continue
            # Be conservative: only treat it as render output if it has state file.
            if not (safe_dir / "render_state.json").exists():
                continue
            if run_id not in known:
                candidates.append(Candidate(run_id=run_id, run_dir=safe_dir))
    except Exception:
        return []

    candidates.sort(key=lambda c: c.run_id)
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Usuń foldery renderu (app/air/render/output/<run_id>) które nie mają właściciela "
            "(Proj.user_id IS NULL) oraz/lub nie istnieją w DB (brak run_id w Proj.render)."
        ),
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=_default_db_path(),
        help="Ścieżka do pliku SQLite users.db (domyślnie: backend-fastapi/users.db).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Wykonaj usunięcie. Bez tej flagi działa jako dry-run.",
    )

    parser.add_argument(
        "--mode",
        choices=[CleanupMode.ORPHANED, CleanupMode.UNTRACKED, CleanupMode.BOTH],
        default=CleanupMode.BOTH,
        help="Zakres sprzątania: orphaned=user_id NULL, untracked=foldery bez rekordu w DB, both=oba.",
    )

    args = parser.parse_args()

    db_path: Path = args.db_path
    if not db_path.exists() or not db_path.is_file():
        print(f"ERROR: DB not found: {db_path}")
        print("Hint: uruchom backend przynajmniej raz albo podaj --db-path do właściwego users.db")
        return 2

    orphaned: list[Candidate] = []
    untracked: list[Candidate] = []
    if args.mode in (CleanupMode.ORPHANED, CleanupMode.BOTH):
        orphaned = _load_orphan_candidates(db_path)
    if args.mode in (CleanupMode.UNTRACKED, CleanupMode.BOTH):
        untracked = _load_untracked_candidates(db_path)

    # De-dup: if a run is orphaned, it can also be untracked only if DB is inconsistent.
    orphaned_ids = {c.run_id for c in orphaned}
    untracked = [c for c in untracked if c.run_id not in orphaned_ids]

    candidates = [*orphaned, *untracked]
    candidates.sort(key=lambda c: c.run_id)

    if not candidates:
        msg = "No candidates found."
        if args.mode == CleanupMode.ORPHANED:
            msg = "No orphaned runs found (Proj.user_id IS NULL)."
        elif args.mode == CleanupMode.UNTRACKED:
            msg = "No untracked run folders found (no matching Proj.render in DB)."
        else:
            msg = "No orphaned or untracked runs found."
        print(msg)
        return 0

    print(f"OUTPUT_ROOT: {OUTPUT_ROOT.resolve()}")
    print(f"DB: {db_path.resolve()}")
    print(f"Mode: {args.mode}")
    print(f"Candidates: {len(candidates)} (orphaned={len(orphaned)} untracked={len(untracked)})")

    removed = 0
    missing = 0

    for c in candidates:
        if not c.run_dir.exists():
            missing += 1
            print(f"[missing] {c.run_id} -> {c.run_dir}")
            continue

        if not c.run_dir.is_dir():
            print(f"[skip:not-a-dir] {c.run_id} -> {c.run_dir}")
            continue

        if args.apply:
            try:
                shutil.rmtree(c.run_dir)
                removed += 1
                print(f"[deleted] {c.run_id} -> {c.run_dir}")
            except Exception as e:
                print(f"[error] {c.run_id} -> {c.run_dir}: {e}")
        else:
            print(f"[dry-run] {c.run_id} -> {c.run_dir}")

    if args.apply:
        print(f"Done. deleted={removed} missing={missing} total={len(candidates)}")
    else:
        print(f"Dry-run done. To delete, rerun with --apply. missing={missing} total={len(candidates)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
