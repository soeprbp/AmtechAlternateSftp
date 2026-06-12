"""Amtech Alternate SFTP staging bundle.

Licensed under the MIT License.

Dependencies:
- Python 3.10 or later
- paramiko (`python -m pip install paramiko`)
- Access to the source EDI share and outbound SFTP network access

The site-specific source root, remote target, and remote directory are supplied
by the launcher script in this folder and can be hand-edited there later.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


BUNDLE_ROOT = Path(__file__).resolve().parent
# Site-specific default source root. Edit in the launcher if the share changes.
DEFAULT_SOURCE_ROOT = Path(r"\\server\share\path\to\amtech\edi\outbound")
DEFAULT_STAGING_ROOT = BUNDLE_ROOT / "staging"
DEFAULT_LOG_DIR = BUNDLE_ROOT / "logs"
DEFAULT_BACKUP_DOC_TYPES = ("DOC1", "DOC2", "DOC3")


@dataclass
class FileSnapshot:
    source_path: str
    staged_path: str
    bytes: int
    line_count: int
    source_sha256: str
    staged_sha256: str
    copy_verified: bool
    last_write_time: str
    record_tag: str


@dataclass
class ArchiveAction:
    source_path: str
    archive_path: str
    source_sha256: str
    archived_sha256: str
    verified_before_move: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Byte-for-byte stage send-ready .dat flat-file EDI documents for temporary SFTP handling. "
            "Defaults are read-only against the network share and write only to local staging."
        )
    )
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_SOURCE_ROOT),
        help="Source EDI root containing the current .dat files plus the Backup folder.",
    )
    parser.add_argument(
        "--staging-root",
        default=str(DEFAULT_STAGING_ROOT),
        help="Local folder where a timestamped SFTP-ready copy set will be written.",
    )
    parser.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR),
        help="Directory where summary and JSON manifest files will be written.",
    )
    parser.add_argument(
        "--mode",
        choices=("current", "backup-batch", "list-backups"),
        default="current",
        help="Stage current root .dat files, stage a selected historical backup batch, or list backup batches.",
    )
    parser.add_argument(
        "--batch-key",
        help="Historical backup batch key, for example 1608JENNIFER1_20260527_145521_5797.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="With --mode backup-batch, stage the most recent complete backup batch.",
    )
    parser.add_argument(
        "--backup-doc-types",
        default=os.environ.get("AMTECH_ALTERNATE_SFTP_BACKUP_DOC_TYPES", ",".join(DEFAULT_BACKUP_DOC_TYPES)),
        help=(
            "Comma-separated backup document name prefixes used by backup-batch mode. "
            "Edit this for each site if backup-batch mode is used."
        ),
    )
    parser.add_argument(
        "--publish-root",
        help="Optional destination folder for a final copy. Use only with --write-share.",
    )
    parser.add_argument(
        "--write-share",
        action="store_true",
        help="Copy staged files to --publish-root. This never deletes files and refuses overwrites unless --overwrite is set.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow --write-share to overwrite files at --publish-root.",
    )
    parser.add_argument(
        "--allow-source-root-write",
        action="store_true",
        help="Allow --publish-root to be the source EDI root. Use only after explicit approval.",
    )
    parser.add_argument(
        "--send-sftp",
        action="store_true",
        help="After staging, upload the staged files with OpenSSH sftp.exe.",
    )
    parser.add_argument(
        "--archive-source-after-send",
        action="store_true",
        help=(
            "After a successful SFTP send, move the staged root .dat files into the source Backup "
            "folder as timestamped .bak files."
        ),
    )
    parser.add_argument(
        "--sftp-target",
        help="SFTP target in user@host form. Can also be set with AMTECH_ALTERNATE_SFTP_TARGET.",
    )
    parser.add_argument(
        "--remote-dir",
        help="Remote SFTP directory. Can also be set with AMTECH_ALTERNATE_SFTP_REMOTE_DIR.",
    )
    parser.add_argument(
        "--sftp-port",
        type=int,
        default=None,
        help="Optional SFTP port. Can also be set with AMTECH_ALTERNATE_SFTP_PORT.",
    )
    parser.add_argument(
        "--identity-file",
        help="Optional SSH private key path. Can also be set with AMTECH_ALTERNATE_SFTP_IDENTITY_FILE.",
    )
    parser.add_argument(
        "--sftp-password-env",
        default="AMTECH_ALTERNATE_SFTP_PASSWORD",
        help="Environment variable containing the SFTP password for Paramiko uploads.",
    )
    parser.add_argument(
        "--sftp-command",
        default="sftp",
        help="SFTP executable to run. Defaults to OpenSSH sftp on PATH.",
    )
    parser.add_argument(
        "--trust-new-host-key",
        action="store_true",
        help=(
            "Allow Paramiko password SFTP to trust and add an unknown host key. "
            "Leave this off for normal use; pre-load the server host key instead."
        ),
    )
    return parser.parse_args()


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def json_default(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def first_record_tag(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        first_line = handle.readline().strip()
    match = re.match(r"(<[^>]+>)", first_line)
    return match.group(1) if match else ""


def normalize_source_root(path: Path) -> str:
    return str(path.resolve()).rstrip("\\/").lower()


def parse_csv_values(raw_value: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in raw_value.split(",") if value.strip())


def current_sources(source_root: Path) -> list[Path]:
    return sorted(path for path in source_root.glob("*.dat") if path.is_file())


def backup_batch_key(path: Path, doc_types: tuple[str, ...]) -> str | None:
    for doc_type in doc_types:
        if not path.name.lower().startswith(doc_type.lower()) or path.suffix.lower() != ".bak":
            continue
        key = path.stem[len(doc_type):]
        return key or None
    return None


def find_backup_batches(source_root: Path, doc_types: tuple[str, ...]) -> dict[str, dict[str, Path]]:
    backup_root = source_root / "Backup"
    batches: dict[str, dict[str, Path]] = {}
    if not backup_root.exists():
        return batches

    for path in backup_root.glob("*.bak"):
        key = backup_batch_key(path, doc_types)
        if not key:
            continue
        doc_type = next(
            candidate
            for candidate in doc_types
            if path.name.lower().startswith(candidate.lower())
        )
        batches.setdefault(key, {})[doc_type] = path
    return batches


def complete_batches(source_root: Path, doc_types: tuple[str, ...]) -> dict[str, dict[str, Path]]:
    return {
        key: files
        for key, files in find_backup_batches(source_root, doc_types).items()
        if all(doc_type in files for doc_type in doc_types)
    }


def list_backup_batches(source_root: Path, doc_types: tuple[str, ...]) -> None:
    batches = complete_batches(source_root, doc_types)
    print(f"Complete backup batches: {len(batches)}")
    for key, files in sorted(
        batches.items(),
        key=lambda item: max(path.stat().st_mtime for path in item[1].values()),
        reverse=True,
    )[:50]:
        latest_mtime = max(path.stat().st_mtime for path in files.values())
        latest_time = datetime.fromtimestamp(latest_mtime).isoformat(timespec="seconds")
        sizes = ", ".join(f"{doc_type}={files[doc_type].stat().st_size}" for doc_type in doc_types)
        print(f"{key} | {latest_time} | {sizes}")


def select_backup_sources(
    source_root: Path,
    batch_key: str | None,
    latest: bool,
    doc_types: tuple[str, ...],
) -> tuple[str, list[Path]]:
    batches = complete_batches(source_root, doc_types)
    if not batches:
        raise RuntimeError(f"No complete backup batches found under {source_root / 'Backup'}")

    if latest:
        selected_key = max(
            batches,
            key=lambda key: max(path.stat().st_mtime for path in batches[key].values()),
        )
        selected = batches[selected_key]
        return selected_key, [selected[doc_type] for doc_type in doc_types]

    if not batch_key:
        raise RuntimeError("--batch-key is required unless --latest is used")

    selected = batches.get(batch_key)
    if selected is None:
        raise RuntimeError(f"Backup batch not found or incomplete: {batch_key}")
    return batch_key, [selected[doc_type] for doc_type in doc_types]


def validate_sources(sources: list[Path]) -> None:
    missing = [str(path) for path in sources if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing source files: " + "; ".join(missing))


def copy_to_staging(sources: list[Path], staging_dir: Path) -> list[FileSnapshot]:
    staging_dir.mkdir(parents=True, exist_ok=False)
    snapshots: list[FileSnapshot] = []

    for source_path in sources:
        staged_name = source_path.name
        staged_path = staging_dir / staged_name
        shutil.copy2(source_path, staged_path)
        stat = source_path.stat()
        source_hash = sha256_file(source_path)
        staged_hash = sha256_file(staged_path)
        snapshots.append(
            FileSnapshot(
                source_path=str(source_path),
                staged_path=str(staged_path),
                bytes=staged_path.stat().st_size,
                line_count=line_count(staged_path),
                source_sha256=source_hash,
                staged_sha256=staged_hash,
                copy_verified=source_hash == staged_hash,
                last_write_time=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                record_tag=first_record_tag(staged_path),
            )
        )

    return snapshots


def write_share_copy(staged_files: list[FileSnapshot], publish_root: Path, overwrite: bool) -> list[str]:
    publish_root.mkdir(parents=True, exist_ok=True)
    published: list[str] = []
    for snapshot in staged_files:
        staged_path = Path(snapshot.staged_path)
        destination = publish_root / staged_path.name
        if destination.exists() and not overwrite:
            raise FileExistsError(f"Publish destination already exists: {destination}")
        shutil.copy2(staged_path, destination)
        published.append(str(destination))
    return published


def unique_archive_path(backup_root: Path, source_path: Path, stamp: str) -> Path:
    candidate = backup_root / f"{source_path.stem}.bak"
    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        candidate = backup_root / f"{source_path.stem}_{stamp}_{counter}.bak"
        if not candidate.exists():
            return candidate
        counter += 1


def archive_sources_after_send(snapshots: list[FileSnapshot], backup_root: Path, stamp: str) -> list[ArchiveAction]:
    backup_root.mkdir(parents=True, exist_ok=True)
    actions: list[ArchiveAction] = []

    for snapshot in snapshots:
        source_path = Path(snapshot.source_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Source file missing before archive: {source_path}")

        current_hash = sha256_file(source_path)
        if current_hash != snapshot.source_sha256:
            raise RuntimeError(f"Source file changed after staging; refusing to archive: {source_path}")

        archive_path = unique_archive_path(backup_root, source_path, stamp)
        shutil.move(str(source_path), str(archive_path))
        archived_hash = sha256_file(archive_path)
        actions.append(
            ArchiveAction(
                source_path=str(source_path),
                archive_path=str(archive_path),
                source_sha256=current_hash,
                archived_sha256=archived_hash,
                verified_before_move=current_hash == archived_hash,
            )
        )

    return actions


def shell_quote_sftp_path(path: str) -> str:
    return '"' + path.replace('"', '\\"') + '"'


def send_sftp(
    staged_files: list[FileSnapshot],
    *,
    sftp_command: str,
    target: str,
    remote_dir: str,
    port: int | None,
    identity_file: str | None,
) -> dict[str, object]:
    batch_lines = [
        f"cd {shell_quote_sftp_path(remote_dir)}",
    ]
    for snapshot in staged_files:
        staged_path = Path(snapshot.staged_path)
        batch_lines.append(f"put {shell_quote_sftp_path(str(staged_path))} {shell_quote_sftp_path(staged_path.name)}")
    batch_lines.append("bye")
    batch_text = "\n".join(batch_lines) + "\n"

    command = [sftp_command, "-b", "-", "-oBatchMode=yes"]
    if port is not None:
        command.extend(["-P", str(port)])
    if identity_file:
        command.extend(["-i", identity_file])
    command.append(target)

    completed = subprocess.run(
        command,
        input=batch_text,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "method": "openssh-sftp",
        "target": mask_sftp_target(target),
        "command": [
            "<identity-file>" if identity_file and part == identity_file else mask_sftp_target(part) if part == target else part
            for part in command
        ],
        "remote_dir": remote_dir,
        "uploaded_files": [Path(snapshot.staged_path).name for snapshot in staged_files],
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "succeeded": completed.returncode == 0,
    }


def parse_sftp_target(target: str) -> tuple[str, str]:
    if "@" not in target:
        raise ValueError("SFTP target must be in user@host form for password uploads")
    username, host = target.split("@", 1)
    if not username or not host:
        raise ValueError("SFTP target must be in user@host form for password uploads")
    return username, host


def mask_sftp_target(target: str) -> str:
    """Keep log files useful without writing SFTP usernames to disk."""
    try:
        _username, host = parse_sftp_target(target)
    except ValueError:
        return "<invalid-target>"
    return f"<user>@{host}"


def send_sftp_with_password(
    staged_files: list[FileSnapshot],
    *,
    target: str,
    remote_dir: str,
    port: int,
    password: str,
    trust_new_host_key: bool,
) -> dict[str, object]:
    try:
        import paramiko
    except ImportError as exc:
        raise RuntimeError("Paramiko is required for password SFTP. Install it with: python -m pip install paramiko") from exc

    username, host = parse_sftp_target(target)
    uploaded_files: list[str] = []
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    # Default to strict host-key checking so a spoofed SFTP host is rejected.
    if trust_new_host_key:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=20,
        )
        with client.open_sftp() as sftp:
            sftp.chdir(remote_dir)
            for snapshot in staged_files:
                staged_path = Path(snapshot.staged_path)
                sftp.put(str(staged_path), staged_path.name)
                uploaded_files.append(staged_path.name)
    finally:
        client.close()

    return {
        "method": "paramiko-password",
        "target": mask_sftp_target(f"{username}@{host}"),
        "port": port,
        "remote_dir": remote_dir,
        "trust_new_host_key": trust_new_host_key,
        "uploaded_files": uploaded_files,
        "returncode": 0,
        "succeeded": True,
    }


def write_manifest(
    log_dir: Path,
    staging_dir: Path,
    mode: str,
    batch_key: str | None,
    snapshots: list[FileSnapshot],
    published: list[str],
    sftp_result: dict[str, object] | None,
    archive_actions: list[ArchiveAction],
) -> tuple[Path, Path]:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = staging_dir.name.replace("amtech_alternate_sftp_", "")
    manifest_path = log_dir / f"amtech_alternate_sftp_{stamp}.json"
    summary_path = log_dir / f"amtech_alternate_sftp_{stamp}.txt"

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "batch_key": batch_key,
        "staging_dir": str(staging_dir),
        "files": [asdict(snapshot) for snapshot in snapshots],
        "published": published,
        "sftp": sftp_result,
        "archived_sources": [asdict(action) for action in archive_actions],
        "safety": {
            "deleted_from_share": False,
            "share_write_required_explicit_flag": True,
            "data_formatting_performed": False,
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2, default=json_default) + "\n", encoding="utf-8")

    lines = [
        "Amtech Alternate SFTP staging summary",
        f"Created at: {manifest['created_at']}",
        f"Mode: {mode}",
        f"Batch key: {batch_key or ''}",
        f"Staging dir: {staging_dir}",
        f"Manifest: {manifest_path}",
        f"Published files: {len(published)}",
        f"SFTP sent: {bool(sftp_result and sftp_result.get('succeeded'))}",
        f"Archived source files: {len(archive_actions)}",
        "Data formatting performed: No",
        "",
        "Files:",
    ]
    for snapshot in snapshots:
        lines.append(
            f"- {Path(snapshot.staged_path).name}: {snapshot.line_count} lines, {snapshot.bytes} bytes, "
            f"{snapshot.record_tag}, copy verified={snapshot.copy_verified}, sha256={snapshot.staged_sha256}"
        )
    if published:
        lines.append("")
        lines.append("Publish destinations:")
        lines.extend(f"- {path}" for path in published)
    if sftp_result:
        lines.append("")
        lines.append("SFTP:")
        command = [str(part) for part in sftp_result.get("command", [])]
        if command:
            lines.append(f"- Method: {sftp_result.get('method', '')}")
            lines.append(f"- Target: {sftp_result.get('target', '')}")
        lines.append(f"- Remote dir: {sftp_result.get('remote_dir', '')}")
        lines.append(f"- Return code: {sftp_result.get('returncode', '')}")
        if sftp_result.get("stderr"):
            lines.append(f"- Stderr: {str(sftp_result['stderr']).strip()}")
    if archive_actions:
        lines.append("")
        lines.append("Archived source files:")
        for action in archive_actions:
            lines.append(f"- {action.source_path} -> {action.archive_path}")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path, summary_path


def main() -> int:
    args = parse_args()
    source_root = Path(args.source_root)
    staging_root = Path(args.staging_root).resolve()
    log_dir = Path(args.log_dir).resolve()
    backup_doc_types = parse_csv_values(args.backup_doc_types)

    if not source_root.exists():
        raise FileNotFoundError(f"Source root not found: {source_root}")

    if args.mode == "list-backups":
        list_backup_batches(source_root, backup_doc_types)
        return 0

    if args.archive_source_after_send:
        if args.mode != "current":
            raise RuntimeError("--archive-source-after-send can only be used with --mode current")
        if not args.send_sftp:
            raise RuntimeError("--archive-source-after-send requires --send-sftp")

    selected_batch_key: str | None = None
    if args.mode == "current":
        sources = current_sources(source_root)
    else:
        selected_batch_key, sources = select_backup_sources(source_root, args.batch_key, args.latest, backup_doc_types)

    validate_sources(sources)

    staging_dir = staging_root / f"amtech_alternate_sftp_{now_stamp()}"
    snapshots = copy_to_staging(sources, staging_dir)
    if any(not snapshot.copy_verified for snapshot in snapshots):
        raise RuntimeError("At least one staged file hash did not match its source; refusing to continue")

    published: list[str] = []
    if args.write_share:
        if not args.publish_root:
            raise RuntimeError("--publish-root is required with --write-share")
        publish_root = Path(args.publish_root)
        if (
            normalize_source_root(publish_root) == normalize_source_root(source_root)
            and not args.allow_source_root_write
        ):
            raise RuntimeError(
                "--publish-root is the source EDI root. Add --allow-source-root-write only after explicit approval."
            )
        published = write_share_copy(snapshots, publish_root, args.overwrite)

    sftp_result: dict[str, object] | None = None
    sftp_error: Exception | None = None
    if args.send_sftp:
        target = args.sftp_target or os.environ.get("AMTECH_ALTERNATE_SFTP_TARGET")
        remote_dir = args.remote_dir or os.environ.get("AMTECH_ALTERNATE_SFTP_REMOTE_DIR")
        raw_port = args.sftp_port or os.environ.get("AMTECH_ALTERNATE_SFTP_PORT")
        identity_file = args.identity_file or os.environ.get("AMTECH_ALTERNATE_SFTP_IDENTITY_FILE")
        password = os.environ.get(args.sftp_password_env)

        if not target:
            raise RuntimeError("--sftp-target or AMTECH_ALTERNATE_SFTP_TARGET is required with --send-sftp")
        if not remote_dir:
            raise RuntimeError("--remote-dir or AMTECH_ALTERNATE_SFTP_REMOTE_DIR is required with --send-sftp")
        port = int(raw_port) if raw_port else None

        try:
            if password:
                sftp_result = send_sftp_with_password(
                    snapshots,
                    target=target,
                    remote_dir=remote_dir,
                    port=port or 22,
                    password=password,
                    trust_new_host_key=args.trust_new_host_key,
                )
            else:
                sftp_result = send_sftp(
                    snapshots,
                    sftp_command=args.sftp_command,
                    target=target,
                    remote_dir=remote_dir,
                    port=port,
                    identity_file=identity_file,
                )
        except Exception as exc:
            sftp_error = exc
            sftp_result = {
                "target": mask_sftp_target(target),
                "port": port or 22,
                "remote_dir": remote_dir,
                "uploaded_files": [],
                "returncode": None,
                "succeeded": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

    archive_actions: list[ArchiveAction] = []
    if args.archive_source_after_send and sftp_result and sftp_result.get("succeeded"):
        archive_actions = archive_sources_after_send(
            snapshots,
            source_root / "Backup",
            datetime.now().strftime("%Y%m%d_%H%M%S"),
        )

    manifest_path, summary_path = write_manifest(
        log_dir,
        staging_dir,
        args.mode,
        selected_batch_key,
        snapshots,
        published,
        sftp_result,
        archive_actions,
    )

    print(f"Staging dir: {staging_dir}")
    print(f"Manifest: {manifest_path}")
    print(f"Summary: {summary_path}")
    print(f"Files staged: {len(snapshots)}")
    print(f"Published files: {len(published)}")
    print(f"SFTP sent: {bool(sftp_result and sftp_result.get('succeeded'))}")
    print(f"Archived source files: {len(archive_actions)}")
    if sftp_error:
        raise RuntimeError(f"SFTP upload failed: {sftp_error}") from sftp_error
    if sftp_result is not None and not sftp_result.get("succeeded"):
        raise RuntimeError(f"SFTP upload failed with return code {sftp_result.get('returncode')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
