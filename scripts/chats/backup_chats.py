"""Back up existing Codex chats without writing to the active Codex home.

Only session JSONL files, the two chat indexes, and known conversation databases
are included. Authentication, settings, plugins and skills are never traversed.
SQLite databases use the online backup API, so committed WAL content is included.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import time
import uuid


class BackupError(RuntimeError):
    """The backup could not be verified; the source is left untouched."""


_DATABASE = re.compile(r"(?:state_\d+|thread_history(?:_\d+)?|\.codex-global-state)\.sqlite\Z")
_SENSITIVE = re.compile(r"auth|credential|secret|(?:^|[._-])token(?:[._-]|$)", re.I)
_SESSION_SUFFIXES = (".jsonl", ".jsonl.zst", ".jsonl.gz", ".jsonl.xz")
_CHUNK = 1024 * 1024


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deadline_check(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise BackupError("Se agotó el tiempo máximo del respaldo.")


def _regular_file(path: Path) -> os.stat_result:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise BackupError(f"No se admite un enlace ni archivo especial: {path.name}")
    return metadata


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _copy_prefix(source: Path, destination: Path, length: int, deadline: float) -> tuple[str, int, bool]:
    digest = hashlib.sha256()
    newlines = 0
    last_byte = b""
    remaining = length
    with source.open("rb") as reader, destination.open("xb") as writer:
        while remaining:
            _deadline_check(deadline)
            block = reader.read(min(_CHUNK, remaining))
            if not block:
                raise BackupError(f"El archivo se redujo durante el respaldo: {source.name}")
            writer.write(block)
            digest.update(block)
            newlines += block.count(b"\n")
            last_byte = block[-1:]
            remaining -= len(block)
        writer.flush()
        os.fsync(writer.fileno())
    return digest.hexdigest(), newlines, length == 0 or last_byte == b"\n"


def _hash_prefix(path: Path, length: int, deadline: float) -> str:
    digest = hashlib.sha256()
    remaining = length
    with path.open("rb") as reader:
        while remaining:
            _deadline_check(deadline)
            block = reader.read(min(_CHUNK, remaining))
            if not block:
                raise BackupError(f"El archivo se redujo durante la verificación: {path.name}")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def _snapshot_jsonl(source: Path, destination: Path, deadline: float) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        _deadline_check(deadline)
        pending = destination.with_name(destination.name + ".partial")
        if pending.exists():
            pending.unlink()
        before = _regular_file(source)
        try:
            digest, newlines, complete = _copy_prefix(source, pending, before.st_size, deadline)
            after_copy = _regular_file(source)
            unchanged_identity = _identity(before) == _identity(after_copy)
            enough_bytes = after_copy.st_size >= before.st_size
            if not unchanged_identity or not enough_bytes:
                raise BackupError(f"El archivo cambió de identidad o se redujo: {source.name}")
            verified = _hash_prefix(source, before.st_size, deadline)
            after_verify = _regular_file(source)
            if (_identity(before) != _identity(after_verify)
                    or after_verify.st_size < before.st_size or verified != digest):
                raise BackupError(f"El contenido cambió durante el respaldo: {source.name}")
            # An append is safe: the captured original prefix was verified twice.
            # A same-size rewrite is retried even if it happened to restore bytes.
            if (after_verify.st_size == before.st_size
                    and after_verify.st_mtime_ns != before.st_mtime_ns):
                raise BackupError(f"El archivo se reescribió durante el respaldo: {source.name}")
            if _hash_prefix(pending, before.st_size, deadline) != digest:
                raise BackupError(f"No coincide el hash del respaldo: {source.name}")
            pending.rename(destination)
            compressed = not source.name.endswith(".jsonl")
            return {
                "kind": "compressed_jsonl" if compressed else "jsonl",
                "compression": source.suffix[1:] if compressed else None,
                "bytes": before.st_size, "sha256": digest,
                "source_mtime_ns": before.st_mtime_ns, "verified_at": _utc(),
                "jsonl_lines": None if compressed else newlines + (0 if complete else 1),
                "last_line_terminated": None if compressed else complete,
                "append_observed": after_verify.st_size > before.st_size,
            }
        except (BackupError, OSError):
            if pending.exists():
                pending.unlink()
            if attempt == 2:
                raise
            _deadline_check(deadline)
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    raise AssertionError("unreachable")


def _sqlite_preconditions(source: Path) -> None:
    # SQLite mode=ro still creates SHM beside a WAL database if it is missing.
    # Refuse before connect rather than silently writing into the active home.
    # Never use immutable=1 for an active source: committed WAL data matters.
    with source.open("rb") as handle:
        header = handle.read(100)
    if len(header) < 100 or header[:16] != b"SQLite format 3\x00":
        raise BackupError(f"La fuente no tiene una cabecera SQLite válida: {source.name}")
    wal = source.with_name(source.name + "-wal")
    shm = source.with_name(source.name + "-shm")
    wal_present = wal.exists() or wal.is_symlink()
    shm_present = shm.exists() or shm.is_symlink()
    if wal_present:
        _regular_file(wal)
    if shm_present:
        _regular_file(shm)
    if (header[18] == 2 or header[19] == 2 or wal_present) and not shm_present:
        raise BackupError(
            f"WAL_WITHOUT_SHM: se rechaza la lectura de {source.name} para no crear SHM en el origen."
        )


def _snapshot_sqlite(source: Path, destination: Path, deadline: float) -> dict:
    before = _regular_file(source)
    _sqlite_preconditions(source)
    pending = destination.with_name(destination.name + ".partial")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # mode=ro prevents CREATE/UPDATE through this connection. Do not use
    # immutable=1: it would ignore an active database's committed WAL pages.
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)) as reader:
        reader.execute("PRAGMA query_only=ON")
        reader.execute("PRAGMA busy_timeout=1000")
        with closing(sqlite3.connect(pending, timeout=1)) as writer:
            def progress(status: int, remaining: int, total: int) -> None:
                _deadline_check(deadline)
            reader.backup(writer, pages=128, progress=progress, sleep=0.05)
            _deadline_check(deadline)
            writer.execute("PRAGMA busy_timeout=1000")
            writer.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            check = writer.execute("PRAGMA integrity_check").fetchall()
            writer.set_progress_handler(None, 0)
            if check != [("ok",)]:
                raise BackupError(f"integrity_check no fue correcto: {source.name}")
    after = _regular_file(source)
    if _identity(before) != _identity(after):
        raise BackupError(f"La base cambió de identidad durante el respaldo: {source.name}")
    pending.rename(destination)
    size = destination.stat().st_size
    return {
        "kind": "sqlite_online_backup", "bytes": size,
        "sha256": _hash_prefix(destination, size, deadline),
        "integrity_check": "ok", "verified_at": _utc(),
    }


def _session_files(source: Path):
    def scan_error(error: OSError) -> None:
        raise error

    def is_link(path: Path) -> bool:
        return path.is_symlink() or getattr(path, "is_junction", lambda: False)()

    for root_name in ("sessions", "archived_sessions"):
        root = source / root_name
        if not root.exists() and not root.is_symlink():
            continue
        if is_link(root) or not root.is_dir():
            raise BackupError(f"La carpeta {root_name} debe ser un directorio real.")
        for current, directories, filenames in os.walk(root, followlinks=False, onerror=scan_error):
            current_path = Path(current)
            for name in directories[:]:
                child = current_path / name
                if _SENSITIVE.search(name):
                    directories.remove(name)
                elif is_link(child):
                    raise BackupError("No se recorren enlaces dentro del historial.")
            for name in sorted(filenames):
                if name.endswith(_SESSION_SUFFIXES) and not _SENSITIVE.search(name):
                    yield current_path / name


def backup_chats(source: Path, destination_parent: Path, timeout: float = 120) -> tuple[Path, dict]:
    source = source.resolve(strict=True)
    destination_parent = destination_parent.resolve()
    if not source.is_dir():
        raise BackupError("El origen debe ser un directorio existente.")
    if destination_parent == source or destination_parent.is_relative_to(source):
        raise BackupError("El respaldo debe guardarse fuera del directorio de Codex.")
    if timeout <= 0:
        raise BackupError("El tiempo máximo debe ser mayor que cero.")
    deadline = time.monotonic() + timeout
    destination_parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = destination_parent / f"chats-{stamp}-{uuid.uuid4().hex[:8]}"
    destination.mkdir(exist_ok=False)
    manifest = {"format_version": 1, "source": str(source), "created_at": _utc(),
                "status": "in_progress", "files": []}
    try:
        for path in _session_files(source):
            relative = path.relative_to(source)
            record = _snapshot_jsonl(path, destination / relative, deadline)
            manifest["files"].append({"path": relative.as_posix(), **record})
        for name in ("session_index.jsonl", "history.jsonl"):
            path = source / name
            if path.exists() or path.is_symlink():
                record = _snapshot_jsonl(path, destination / name, deadline)
                manifest["files"].append({"path": name, **record})
        for path in sorted(source.iterdir()):
            if _DATABASE.fullmatch(path.name):
                _deadline_check(deadline)
                record = _snapshot_sqlite(path, destination / path.name, deadline)
                manifest["files"].append({"path": path.name, **record})
        manifest["status"] = "verified"
        manifest["completed_at"] = _utc()
        manifest["summary"] = {
            "session_files": sum(f["path"].startswith(("sessions/", "archived_sessions/"))
                                 for f in manifest["files"]),
            "sqlite_databases": sum(f["kind"] == "sqlite_online_backup" for f in manifest["files"]),
            "total_bytes": sum(f["bytes"] for f in manifest["files"]),
            "partial_last_lines": sum(f.get("last_line_terminated") is False for f in manifest["files"]),
        }
    except (BackupError, OSError, sqlite3.Error) as exc:
        manifest["status"] = "failed"
        manifest["error_type"] = type(exc).__name__
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        raise BackupError(f"Respaldo incompleto en {destination}: {exc}") from exc
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path,
                        help="Directorio padre; cada respaldo crea una subcarpeta única.")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    try:
        destination, manifest = backup_chats(args.source, args.destination, args.timeout)
    except (BackupError, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": manifest["status"], "destination": str(destination),
                      **manifest["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
