"""
SysMho — CLI entry points.

All functions in this module are registered as console_scripts in pyproject.toml.
Run any command via: uv run <command-name>
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTAINER_NAME = "sysmho-postgres"
SCHEMA_FILE = PROJECT_ROOT / "src" / "database" / "schema.sql"
MIGRATIONS_DIR = PROJECT_ROOT / "src" / "database"
MIGRATION_PATTERN = re.compile(r"^migration_v(\d+)_(\d+)_(\d+)\.sql$")
DEFAULT_SEED = PROJECT_ROOT / "src" / "database" / "seed" / "sysmho_full.sql"
BACKUP_DIR = PROJECT_ROOT / "backups"
MODELS_DIR = PROJECT_ROOT / "src" / "ai" / "models"


# ── Shared helpers ────────────────────────────────────────────────────────────


def _load_env(env_file: str) -> dict[str, str]:
    """Parse a .env file and return key-value pairs. Does NOT set os.environ."""
    env_path = PROJECT_ROOT / env_file
    result: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                result[key.strip()] = val.strip()
    return result


def _db_url_from_env(env_file: str = ".env") -> str:
    """Build a postgresql:// URL from an env file."""
    env = _load_env(env_file)
    host = env.get("DB_HOST", "localhost")
    port = env.get("DB_PORT", "5432")
    user = env.get("DB_USER", "postgres")
    password = env.get("DB_PASSWORD", "postgres")
    name = env.get("DB_NAME", "sysmho")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def _db_creds_from_env(env_file: str = ".env") -> tuple[str, str, str, str, str]:
    """Return (host, port, user, password, dbname) from env file."""
    env = _load_env(env_file)
    return (
        env.get("DB_HOST", "localhost"),
        env.get("DB_PORT", "5432"),
        env.get("DB_USER", "postgres"),
        env.get("DB_PASSWORD", "postgres"),
        env.get("DB_NAME", "sysmho"),
    )


def _get_sorted_migrations() -> list[Path]:
    """Discover migration_vX_Y_Z.sql files and return sorted by version."""
    migrations: list[tuple[tuple[int, int, int], Path]] = []
    for f in MIGRATIONS_DIR.iterdir():
        m = MIGRATION_PATTERN.match(f.name)
        if m:
            version = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            migrations.append((version, f))
    migrations.sort(key=lambda x: x[0])
    return [f for _, f in migrations]


def _docker_exec(
    args: list[str], *, check: bool = True, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run a command inside the sysmho-postgres container."""
    cmd = ["docker", "exec", CONTAINER_NAME] + args
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def _container_running() -> bool:
    """Check if sysmho-postgres container is running."""
    r = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={CONTAINER_NAME}"],
        capture_output=True,
        text=True,
    )
    return bool(r.stdout.strip())


def _container_exists() -> bool:
    """Check if sysmho-postgres container exists (running or stopped)."""
    r = subprocess.run(
        ["docker", "ps", "-aq", "-f", f"name={CONTAINER_NAME}"],
        capture_output=True,
        text=True,
    )
    return bool(r.stdout.strip())


def _wait_for_healthy(timeout: int = 60) -> bool:
    """Poll container health status until healthy or timeout."""
    start = time.time()
    print("  Waiting for healthy status...", end="", flush=True)
    while time.time() - start < timeout:
        r = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER_NAME],
            capture_output=True,
            text=True,
        )
        status = r.stdout.strip()
        if status == "healthy":
            print(" ready.")
            return True
        if r.returncode != 0:
            print(f"\n  Container '{CONTAINER_NAME}' not found.")
            return False
        print(".", end="", flush=True)
        time.sleep(2)
    print(f"\n  Timeout ({timeout}s): container did not become healthy.")
    return False


# ── LOCAL entry points ────────────────────────────────────────────────────────


def db_start() -> None:
    """Check if local PostgreSQL is reachable."""
    import asyncpg  # noqa: PLC0415

    host, port, user, password, dbname = _db_creds_from_env()

    async def _ping() -> None:
        conn = await asyncpg.connect(
            host=host, port=int(port), user=user, password=password, database=dbname
        )
        await conn.close()

    try:
        asyncio.run(_ping())
        print(f"PostgreSQL is running at {host}:{port}, database: {dbname}")
    except Exception as exc:
        print(f"Cannot connect to PostgreSQL: {exc}")
        print("Start PostgreSQL or use `uv run db-start-docker`")
        sys.exit(1)


def db_stop() -> None:
    """Print platform-specific instructions to stop local PostgreSQL."""
    platform = sys.platform
    print("Stop local PostgreSQL:")
    if platform == "win32":
        print("  net stop postgresql-x64-17")
        print("  (or stop the service via Services panel)")
    elif platform == "darwin":
        print("  brew services stop postgresql")
    else:
        print("  sudo systemctl stop postgresql")
    print()
    print("To stop Docker PostgreSQL instead: uv run db-stop-docker")


def db_status() -> None:
    """Show local PostgreSQL version and table count."""
    import asyncpg  # noqa: PLC0415

    host, port, user, password, dbname = _db_creds_from_env()

    async def _status() -> None:
        conn = await asyncpg.connect(
            host=host, port=int(port), user=user, password=password, database=dbname
        )
        try:
            version = await conn.fetchval("SELECT version()")
            table_count = await conn.fetchval(
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"
            )
            print(f"  Host:     {host}:{port}")
            print(f"  Database: {dbname}")
            print(f"  Version:  {version}")
            print(f"  Tables:   {table_count}")
        finally:
            await conn.close()

    try:
        asyncio.run(_status())
    except Exception as exc:
        print(f"Cannot connect to PostgreSQL: {exc}")
        sys.exit(1)


def db_migrate() -> None:
    """Apply schema.sql and all migrations to local PostgreSQL."""
    import asyncpg  # noqa: PLC0415

    host, port, user, password, dbname = _db_creds_from_env()

    async def _migrate() -> None:
        conn = await asyncpg.connect(
            host=host, port=int(port), user=user, password=password, database=dbname
        )
        try:
            sql = SCHEMA_FILE.read_text(encoding="utf-8")
            await conn.execute(sql)
            print(f"  Applied: schema.sql")

            for migration in _get_sorted_migrations():
                sql = migration.read_text(encoding="utf-8")
                await conn.execute(sql)
                print(f"  Applied: {migration.name}")

            table_count = await conn.fetchval(
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"
            )
            print(f"\n  Migration complete. {table_count} tables in '{dbname}'.")
        finally:
            await conn.close()

    try:
        asyncio.run(_migrate())
    except Exception as exc:
        print(f"Migration failed: {exc}")
        sys.exit(1)


def db_seed() -> None:
    """Load seed data into local PostgreSQL using psql."""
    parser = argparse.ArgumentParser(description="Load seed data into PostgreSQL")
    parser.add_argument("--file", type=Path, default=DEFAULT_SEED, help="SQL seed file")
    args = parser.parse_args(sys.argv[1:])

    seed_file: Path = args.file
    if not seed_file.exists():
        print(f"Seed file not found: {seed_file}")
        sys.exit(1)

    if not shutil.which("psql"):
        print("psql not found. Install PostgreSQL client tools or use `uv run db-seed-docker`")
        sys.exit(1)

    host, port, user, password, dbname = _db_creds_from_env()
    env = os.environ.copy()
    env["PGPASSWORD"] = password

    print(f"  Loading seed: {seed_file.name} ...")
    result = subprocess.run(
        ["psql", "-h", host, "-p", port, "-U", user, "-d", dbname, "-f", str(seed_file)],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Seed failed:\n{result.stderr}")
        sys.exit(1)
    print("  Seed loaded successfully.")


def db_backup() -> None:
    """Backup local PostgreSQL database and/or model files."""
    parser = argparse.ArgumentParser(description="Backup database and/or models")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--db-only", action="store_true", help="Database dump only")
    group.add_argument("--models-only", action="store_true", help="Model files only")
    args = parser.parse_args(sys.argv[1:])

    do_db = args.db_only or (not args.db_only and not args.models_only)
    do_models = args.models_only or (not args.db_only and not args.models_only)

    if do_db and not shutil.which("pg_dump"):
        print("pg_dump not found. Install PostgreSQL client tools or use `uv run db-backup-docker`")
        sys.exit(1)

    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    host, port, user, password, dbname = _db_creds_from_env()

    if do_db:
        out = BACKUP_DIR / f"sysmho_{ts}.sql"
        print(f"  Dumping database → {out.name} ...")
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        result = subprocess.run(
            ["pg_dump", "-h", host, "-p", port, "-U", user, dbname],
            env=env,
            capture_output=True,
        )
        if result.returncode != 0:
            print(f"  pg_dump failed: {result.stderr.decode()}")
            sys.exit(1)
        out.write_bytes(result.stdout)
        size_mb = out.stat().st_size / (1024 * 1024)
        print(f"  Database backed up ({size_mb:.1f} MB)")

    if do_models:
        models_out = BACKUP_DIR / f"sysmho_{ts}_models"
        if MODELS_DIR.exists():
            shutil.copytree(MODELS_DIR, models_out)
            print(f"  Models backed up → {models_out.name}/")
        else:
            print(f"  Models directory not found: {MODELS_DIR.relative_to(PROJECT_ROOT)}")

    print(f"\n  Backup complete → backups/sysmho_{ts}*")


# ── DOCKER entry points ──────────────────────────────────────────────────────


def db_start_docker() -> None:
    """Start the sysmho-postgres Docker container."""
    host, port, user, password, dbname = _db_creds_from_env()

    if _container_running():
        print(f"{CONTAINER_NAME} is already running.")
        return

    if _container_exists():
        print(f"  Starting existing container '{CONTAINER_NAME}'...")
        subprocess.run(["docker", "start", CONTAINER_NAME], check=True)
    else:
        print(f"  Creating container '{CONTAINER_NAME}'...")
        subprocess.run(
            [
                "docker", "run", "-d",
                "--name", CONTAINER_NAME,
                "-e", f"POSTGRES_USER={user}",
                "-e", f"POSTGRES_PASSWORD={password}",
                "-e", f"POSTGRES_DB={dbname}",
                "-p", "5432:5432",
                "-v", "sysmho_pgdata:/var/lib/postgresql/data",
                "--health-cmd", f"pg_isready -U {user} -d {dbname}",
                "--health-interval", "10s",
                "--health-timeout", "5s",
                "--health-retries", "5",
                "postgres:17",
            ],
            check=True,
        )

    if not _wait_for_healthy(timeout=60):
        sys.exit(1)

    print(f"{CONTAINER_NAME} is running on port 5432")


def db_stop_docker() -> None:
    """Stop the sysmho-postgres Docker container."""
    if not _container_running():
        print(f"{CONTAINER_NAME} is not running.")
        return

    subprocess.run(["docker", "stop", CONTAINER_NAME], check=True)
    print("Container stopped. Data volume preserved.")
    print("To also remove volume: docker volume rm sysmho_pgdata")


def db_status_docker() -> None:
    """Show status of the sysmho-postgres Docker container."""
    if not _container_exists():
        print(f"Container '{CONTAINER_NAME}' not found.")
        sys.exit(1)

    r = subprocess.run(
        ["docker", "inspect", CONTAINER_NAME],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"Cannot inspect container: {r.stderr}")
        sys.exit(1)

    info = json.loads(r.stdout)[0]
    state = info["State"]
    running = state.get("Running", False)
    status_str = state.get("Status", "unknown")
    health = state.get("Health", {}).get("Status", "n/a")
    started_at = state.get("StartedAt", "")

    print(f"  Container: {CONTAINER_NAME}")
    print(f"  Status:    {status_str}")
    print(f"  Health:    {health}")
    print(f"  Started:   {started_at}")

    if running:
        import asyncpg  # noqa: PLC0415

        host, port, user, password, dbname = _db_creds_from_env()

        async def _ping() -> None:
            conn = await asyncpg.connect(
                host="localhost", port=5432, user=user, password=password, database=dbname
            )
            version = await conn.fetchval("SELECT version()")
            await conn.close()
            print(f"  PostgreSQL: {version}")

        try:
            asyncio.run(_ping())
        except Exception as exc:
            print(f"  PostgreSQL ping failed: {exc}")


def db_migrate_docker() -> None:
    """Apply schema and migrations inside the Docker container."""
    if not _container_running():
        print(f"Container '{CONTAINER_NAME}' is not running. Start it first: uv run db-start-docker")
        sys.exit(1)

    _host, _port, user, _password, dbname = _db_creds_from_env()

    def _apply(filepath: Path) -> None:
        container_path = f"/tmp/{filepath.name}"
        subprocess.run(
            ["docker", "cp", str(filepath), f"{CONTAINER_NAME}:{container_path}"],
            check=True,
            capture_output=True,
        )
        result = _docker_exec(
            ["psql", "-U", user, "-d", dbname, "-f", container_path],
            check=False,
            capture=True,
        )
        _docker_exec(["rm", "-f", container_path], check=False, capture=True)
        if result.returncode != 0:
            print(f"  ERROR applying {filepath.name}:\n{result.stderr}")
            sys.exit(1)
        print(f"  Applied: {filepath.name}")

    _apply(SCHEMA_FILE)
    for migration in _get_sorted_migrations():
        _apply(migration)

    result = _docker_exec(
        [
            "psql", "-U", user, "-d", dbname, "-t", "-A", "-c",
            "SELECT count(*) FROM pg_tables WHERE schemaname = 'public';",
        ],
        capture=True,
    )
    table_count = result.stdout.strip()
    print(f"\n  Migration complete. {table_count} tables in '{dbname}'.")


def db_seed_docker() -> None:
    """Load seed data into Docker PostgreSQL."""
    parser = argparse.ArgumentParser(description="Load seed data (Docker)")
    parser.add_argument("--file", type=Path, default=DEFAULT_SEED, help="SQL seed file")
    args = parser.parse_args(sys.argv[1:])

    seed_file: Path = args.file
    if not seed_file.exists():
        print(f"Seed file not found: {seed_file}")
        sys.exit(1)

    if not _container_running():
        print(f"Container '{CONTAINER_NAME}' is not running. Start it first: uv run db-start-docker")
        sys.exit(1)

    _host, _port, user, _password, dbname = _db_creds_from_env()

    print(f"  Loading seed: {seed_file.name} ...")
    subprocess.run(
        ["docker", "cp", str(seed_file), f"{CONTAINER_NAME}:/tmp/seed.sql"],
        check=True,
    )
    result = _docker_exec(
        ["psql", "-U", user, "-d", dbname, "-f", "/tmp/seed.sql"],
        check=False,
        capture=True,
    )
    _docker_exec(["rm", "-f", "/tmp/seed.sql"], check=False, capture=True)

    if result.returncode != 0:
        print(f"  Seed failed:\n{result.stderr}")
        sys.exit(1)

    copy_lines = [l for l in result.stdout.splitlines() if l.startswith("COPY ")]
    total_rows = sum(int(l.split()[1]) for l in copy_lines if l.split()[1].isdigit())
    print(f"  Seed loaded. ({total_rows:,} rows across {len(copy_lines)} tables)")


def db_backup_docker() -> None:
    """Backup Docker PostgreSQL database and/or local model files."""
    parser = argparse.ArgumentParser(description="Backup database and/or models (Docker)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--db-only", action="store_true", help="Database dump only")
    group.add_argument("--models-only", action="store_true", help="Model files only")
    args = parser.parse_args(sys.argv[1:])

    do_db = args.db_only or (not args.db_only and not args.models_only)
    do_models = args.models_only or (not args.db_only and not args.models_only)

    if do_db and not _container_running():
        print(f"Container '{CONTAINER_NAME}' is not running. Start it first: uv run db-start-docker")
        sys.exit(1)

    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    _host, _port, user, _password, dbname = _db_creds_from_env()

    if do_db:
        out = BACKUP_DIR / f"sysmho_{ts}.sql"
        print(f"  Dumping database → {out.name} ...")
        result = subprocess.run(
            ["docker", "exec", CONTAINER_NAME, "pg_dump", "-U", user, dbname],
            capture_output=True,
        )
        if result.returncode != 0:
            print(f"  pg_dump failed: {result.stderr.decode()}")
            sys.exit(1)
        out.write_bytes(result.stdout)
        size_mb = out.stat().st_size / (1024 * 1024)
        print(f"  Database backed up ({size_mb:.1f} MB)")

    if do_models:
        models_out = BACKUP_DIR / f"sysmho_{ts}_models"
        if MODELS_DIR.exists():
            shutil.copytree(MODELS_DIR, models_out)
            print(f"  Models backed up → {models_out.name}/")
        else:
            print(f"  Models directory not found: {MODELS_DIR.relative_to(PROJECT_ROOT)}")

    print(f"\n  Backup complete → backups/sysmho_{ts}*")


# ── Application entry points ─────────────────────────────────────────────────


def engine() -> None:
    """Launch the SysMho AI Engine."""
    sys.exit(subprocess.call([sys.executable, "-m", "src.main"]))


def dashboard() -> None:
    """Launch the SysMho Dashboard API."""
    sys.exit(
        subprocess.call(
            [sys.executable, "-m", "uvicorn", "src.dashboard.api:app", "--host", "0.0.0.0", "--port", "8000"]
        )
    )


def test() -> None:
    """Run the test suite via pytest."""
    sys.exit(subprocess.call([sys.executable, "-m", "pytest"] + sys.argv[1:]))
