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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Usuń foldery renderu (app/air/render/output/<run_id>) bez właściciela (Proj.user_id IS NULL).",
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

    args = parser.parse_args()

    db_path: Path = args.db_path
    if not db_path.exists() or not db_path.is_file():
        print(f"ERROR: DB not found: {db_path}")
        print("Hint: uruchom backend przynajmniej raz albo podaj --db-path do właściwego users.db")
        return 2

    candidates = _load_orphan_candidates(db_path)

    if not candidates:
        print("No orphaned runs found (Proj.user_id IS NULL).")
        return 0

    print(f"OUTPUT_ROOT: {OUTPUT_ROOT.resolve()}")
    print(f"DB: {db_path.resolve()}")
    print(f"Candidates: {len(candidates)}")

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
