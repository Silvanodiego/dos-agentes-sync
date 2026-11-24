"""Read-only coverage guard for Codex's authoritative thread rollout paths.

No chat content, title, credentials or configuration is read. SQLite is opened
with mode=ro and copied into memory through its online backup API. This checks
file presence, not history completeness or whether a rebuild is safe.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import json
import ntpath
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import time


class CoverageError(RuntimeError):
    """The inventory could not be read safely or its schema is unsupported."""


_DATABASE_NAME = re.compile(r"state_\d+\.sqlite\Z", re.I)
_CODECS = {".zst": "zstd", ".gz": "gzip", ".xz": "xz"}


def normalize_windows_path(value: str) -> str:
    """Remove Win32 extended prefixes without losing drive or UNC semantics."""
    value = value.replace("/", "\\")
    if value.lower().startswith("\\\\?\\unc\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    if value.startswith("\\\\.\\"):
        raise CoverageError("No se admiten rutas de dispositivo Win32.")
    return ntpath.normpath(value)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def _regular(path: Path) -> bool:
    try:
        return not _is_link(path) and stat.S_ISREG(path.lstat().st_mode)
    except (OSError, ValueError):
        return False


def locate_database(source: Path) -> tuple[Path, Path]:
    source = source.expanduser().absolute()
    if source.is_dir():
        candidates = sorted(p for p in source.iterdir() if _DATABASE_NAME.fullmatch(p.name))
        if len(candidates) != 1:
            raise CoverageError(
                "Se necesita exactamente un state_*.sqlite; indicá --source con la base exacta."
            )
        database, root = candidates[0], source
    else:
        database, root = source, source.parent
    if not _DATABASE_NAME.fullmatch(database.name) or not _regular(database):
        raise CoverageError("--source debe ser un state_*.sqlite regular o su carpeta.")
    if _is_link(root):
        raise CoverageError("La carpeta fuente no puede ser un enlace o junction.")
    return database, root


def _sqlite_preconditions(database: Path) -> None:
    # mode=ro can still create SQLite's SHM beside a WAL-mode database. Inspect
    # the header before opening; never use immutable=1 to bypass WAL locking.
    with database.open("rb") as handle:
        header = handle.read(100)
    if len(header) < 100 or header[:16] != b"SQLite format 3\x00":
        raise CoverageError("La fuente no tiene una cabecera SQLite válida.")
    wal = database.with_name(database.name + "-wal")
    shm = database.with_name(database.name + "-shm")
    wal_mode = header[18] == 2 or header[19] == 2
    if (wal_mode or wal.exists()) and not _regular(shm):
        raise CoverageError(
            "WAL_WITHOUT_SHM: lectura rechazada para no crear archivos junto a la base."
        )
    if wal.exists() and not _regular(wal):
        raise CoverageError("El WAL no es un archivo regular.")


def read_threads(database: Path, timeout: float = 15.0) -> tuple[list[dict], list[str]]:
    _sqlite_preconditions(database)
    before = database.stat()
    deadline = time.monotonic() + timeout
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)) as reader:
        reader.execute("PRAGMA query_only=ON")
        reader.execute("PRAGMA busy_timeout=1000")
        with closing(sqlite3.connect(":memory:")) as snapshot:
            def progress(status: int, remaining: int, total: int) -> None:
                if time.monotonic() >= deadline:
                    raise CoverageError("Se agotó el tiempo al obtener el snapshot SQLite.")
            reader.backup(snapshot, pages=128, progress=progress, sleep=0.02)
            after = database.stat()
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                raise CoverageError("La base cambió de identidad durante el snapshot.")
            snapshot.execute("PRAGMA query_only=ON")
            snapshot.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            columns = {r[1] for r in snapshot.execute('PRAGMA table_info("threads")')}
            if not {"id", "rollout_path"}.issubset(columns):
                raise CoverageError("threads no contiene id y rollout_path; esquema no compatible.")
            missing = [name for name in ("has_user_event", "source") if name not in columns]
            fields = ['"id"', '"rollout_path"']
            fields += ['"' + name + '"' if name in columns else "NULL" for name in ("has_user_event", "source")]
            rows = []
            for thread_id, rollout, user_event, source in snapshot.execute(
                "SELECT " + ", ".join(fields) + ' FROM "threads" ORDER BY "id"'
            ):
                if not isinstance(thread_id, str) or not thread_id:
                    raise CoverageError("Hay un thread sin identificador válido.")
                if rollout is not None and not isinstance(rollout, str):
                    raise CoverageError("Hay un rollout_path que no es texto ni NULL.")
                rows.append({
                    "thread_id": thread_id,
                    "rollout_path": rollout,
                    "has_user_event": int(user_event) if user_event in (0, 1) else None,
                    "source": source if isinstance(source, str) else None,
                })
            return rows, missing


def resolve_rollout(value: str | None, root: Path) -> Path | None:
    if not value or "\x00" in value:
        return None
    if os.name == "nt":
        normalized = normalize_windows_path(value)
        # A drive-relative C:foo cannot safely be interpreted against this root.
        drive, tail = ntpath.splitdrive(normalized)
        if drive and not tail.startswith("\\"):
            return None
        result = Path(normalized)
    else:
        # Native paths keep the guard testable on non-Windows systems. A Windows
        # absolute path there is unavailable, never guessed into another root.
        if ntpath.splitdrive(value)[0] or value.startswith("\\"):
            return None
        result = Path(value)
    return result if result.is_absolute() else root / result


def classify_rollout(value: str | None, root: Path) -> dict:
    path = resolve_rollout(value, root)
    if path is None:
        return {"coverage": "missing", "reason": "invalid_or_empty_path", "normalized_path": None}
    normalized = str(path)
    suffix = path.suffix.lower()
    if suffix in _CODECS and path.name[:-len(suffix)].lower().endswith(".jsonl"):
        logical = path.with_suffix("")
    elif suffix == ".jsonl":
        logical = path
    else:
        return {"coverage": "missing", "reason": "unsupported_rollout_extension", "normalized_path": normalized}
    candidates = [path]
    candidates += [candidate for candidate in [logical] + [Path(str(logical) + s) for s in _CODECS] if candidate != path]
    present = [candidate for candidate in candidates if _regular(candidate)]
    if not present:
        return {"coverage": "missing", "reason": "authoritative_path_and_containers_absent", "normalized_path": normalized}
    selected = present[0]
    return {
        "coverage": "exact" if selected == path else "container_variant",
        "normalized_path": normalized,
        "resolved_path": str(selected),
        "compression": _CODECS.get(selected.suffix.lower(), "none"),
        "representations_present": len(present),
        "bytes": selected.stat().st_size,
    }


def audit_source(source: Path, *, strict: bool = True, timeout: float = 15.0) -> dict:
    database, root = locate_database(source)
    threads, missing_columns = read_threads(database, timeout)
    for row in threads:
        row.update(classify_rollout(row["rollout_path"], root))
    missing = [row for row in threads if row["coverage"] == "missing"]
    user_missing = [row for row in missing if row["has_user_event"] == 1]
    unknown_missing = [row for row in missing if row["has_user_event"] is None]
    # has_user_event=0 is not evidence that the chat has no human history.
    # This guard always requires every authoritative rollout, irrespective of
    # source or this flag. ``strict`` remains an accepted compatibility option.
    blocked = bool(missing)
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": str(database),
        "state_root": str(root),
        "snapshot": "sqlite_readonly_online_backup_in_memory",
        "scope": "presence_only_no_chat_content_read",
        "strict": True,
        "metadata_columns_missing": missing_columns,
        "summary": {
            "threads": len(threads), "covered": len(threads) - len(missing),
            "missing": len(missing), "user_event_missing": len(user_missing),
            "unknown_user_event_missing": len(unknown_missing),
            "by_coverage": dict(sorted(Counter(r["coverage"] for r in threads).items())),
            "by_source": dict(sorted(Counter(r["source"] or "<unknown>" for r in threads).items())),
            "by_has_user_event": dict(sorted(Counter(str(r["has_user_event"]) for r in threads).items())),
            "missing_by_source": dict(sorted(Counter(r["source"] or "<unknown>" for r in missing).items())),
            "missing_by_has_user_event": dict(sorted(Counter(str(r["has_user_event"]) for r in missing).items())),
            "by_compression": dict(sorted(Counter(r["compression"] for r in threads if "compression" in r).items())),
        },
        "guard_passed": not blocked,
        "exit_code": 2 if blocked else 0,
        "missing": missing,
        "threads": threads,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Codex home o state_*.sqlite exacto")
    parser.add_argument("--output", type=Path,
                        help="Manifest JSON local: fuera del Codex home o en su carpeta visualizations")
    parser.add_argument("--strict", action="store_true", default=True,
                        help="Compatibilidad: el guard siempre exige todos los rollouts")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)
    try:
        if args.timeout <= 0:
            raise CoverageError("--timeout debe ser positivo.")
        report = audit_source(args.source, strict=args.strict, timeout=args.timeout)
        if args.output:
            output = args.output.expanduser().absolute()
            root = Path(report["state_root"]).resolve()
            resolved_output = output.resolve()
            if (resolved_output.is_relative_to(root)
                    and not resolved_output.is_relative_to(root / "visualizations")):
                raise CoverageError(
                    "El manifest debe guardarse fuera del estado Codex o en visualizations."
                )
            # Never silently overwrite another manifest or a local file.
            with output.open("x", encoding="utf-8") as handle:
                json.dump(report, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        console = {key: value for key, value in report.items() if key != "threads"}
        if args.output:
            console["manifest"] = str(args.output.absolute())
        print(json.dumps(console, ensure_ascii=False, indent=2))
        return report["exit_code"]
    except (CoverageError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"guard_passed": False, "exit_code": 3, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
