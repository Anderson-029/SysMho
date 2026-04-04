"""
SysMho — Database Setup Script.

Cross-platform script that initializes the PostgreSQL database:
  1. Waits for the Docker container (sysmho-postgres) to be healthy.
  2. Applies schema.sql (idempotent — CREATE TABLE IF NOT EXISTS).
  3. Applies all migrations in version order.
  4. Optionally loads seed data from src/database/seed/sysmho_full.sql.

Usage:
    uv run python scripts/setup_db.py           # schema + migrations only
    uv run python scripts/setup_db.py --seed    # also load seed data

Prerequisites:
    - Docker container running:  docker compose up -d
    - (For --seed) Place sysmho_full.sql in src/database/seed/
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTAINER_NAME = "sysmho-postgres"
SCHEMA_FILE = PROJECT_ROOT / "src" / "database" / "schema.sql"
MIGRATIONS_DIR = PROJECT_ROOT / "src" / "database"
SEED_DIR = PROJECT_ROOT / "src" / "database" / "seed"
SEED_FILE = SEED_DIR / "sysmho_full.sql"

MIGRATION_PATTERN = re.compile(r"^migration_v(\d+)_(\d+)_(\d+)\.sql$")


def run_docker(args: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = ["docker", "exec", CONTAINER_NAME] + args
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def get_db_env() -> tuple[str, str]:
    """Read DB_USER and DB_NAME from .env, falling back to defaults."""
    env_file = PROJECT_ROOT / ".env"
    user, name = "postgres", "sysmho"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DB_USER="):
                user = line.split("=", 1)[1].strip()
            elif line.startswith("DB_NAME="):
                name = line.split("=", 1)[1].strip()
    return user, name


def wait_for_container(timeout: int = 60) -> None:
    """Wait until the Postgres container reports healthy."""
    print(f"  Waiting for container '{CONTAINER_NAME}' to be healthy...", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER_NAME],
            capture_output=True, text=True,
        )
        status = result.stdout.strip()
        if status == "healthy":
            print(" ready.")
            return
        if result.returncode != 0:
            print(f"\n  Container '{CONTAINER_NAME}' not found. Is 'docker compose up -d' running?")
            sys.exit(1)
        print(".", end="", flush=True)
        time.sleep(2)
    print(f"\n  Timeout ({timeout}s): container did not become healthy.")
    sys.exit(1)


def apply_sql_file(filepath: Path, db_user: str, db_name: str, *, label: str = "") -> None:
    """Copy a SQL file into the container and execute it with psql."""
    container_path = f"/tmp/{filepath.name}"
    tag = label or filepath.name

    subprocess.run(
        ["docker", "cp", str(filepath), f"{CONTAINER_NAME}:{container_path}"],
        check=True, capture_output=True,
    )
    result = run_docker(
        ["psql", "-U", db_user, "-d", db_name, "-f", container_path],
        check=False, capture=True,
    )

    run_docker(["rm", "-f", container_path], check=False, capture=True)

    if result.returncode != 0:
        print(f"  ERROR applying {tag}:")
        print(result.stderr)
        sys.exit(1)
    print(f"  Applied: {tag}")


def get_sorted_migrations() -> list[Path]:
    """Discover migration_vX_Y_Z.sql files and return them sorted by version."""
    migrations = []
    for f in MIGRATIONS_DIR.iterdir():
        m = MIGRATION_PATTERN.match(f.name)
        if m:
            version = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            migrations.append((version, f))
    migrations.sort(key=lambda x: x[0])
    return [f for _, f in migrations]


def load_seed_data(db_user: str, db_name: str, step: int = 2, total: str = "3") -> None:
    """Copy the seed dump into the container and restore it."""
    if not SEED_FILE.exists():
        print(f"\n  Seed file not found: {SEED_FILE.relative_to(PROJECT_ROOT)}")
        print("  To load historical data, place sysmho_full.sql in src/database/seed/")
        print("  Skipping seed data.")
        return

    size_mb = SEED_FILE.stat().st_size / (1024 * 1024)
    print(f"\n[{step}/{total}] Loading seed data ({size_mb:.0f} MB) — this may take a few minutes...")

    container_path = "/tmp/sysmho_full.sql"
    print("  Copying file into container...", end="", flush=True)
    subprocess.run(
        ["docker", "cp", str(SEED_FILE), f"{CONTAINER_NAME}:{container_path}"],
        check=True,
    )
    print(" done.")

    print("  Restoring...", end="", flush=True)
    result = run_docker(
        ["psql", "-U", db_user, "-d", db_name, "-f", container_path],
        check=False, capture=True,
    )
    run_docker(["rm", "-f", container_path], check=False, capture=True)

    if result.returncode != 0:
        print(f" failed.\n{result.stderr}")
        sys.exit(1)

    copy_lines = [l for l in result.stdout.splitlines() if l.startswith("COPY ")]
    total_rows = sum(int(l.split()[1]) for l in copy_lines if l.split()[1].isdigit())
    print(f" done. ({total_rows:,} rows loaded across {len(copy_lines)} tables)")


def verify_tables(db_user: str, db_name: str) -> None:
    """Print a summary of tables and row counts."""
    result = run_docker(
        ["psql", "-U", db_user, "-d", db_name, "-t", "-A", "-c",
         "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"],
        check=False, capture=True,
    )
    tables = [t.strip() for t in result.stdout.strip().splitlines() if t.strip()]
    print(f"\n  Database '{db_name}' has {len(tables)} tables: {', '.join(tables)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SysMho — Database Setup")
    parser.add_argument("--seed", action="store_true", help="Also load seed data from src/database/seed/sysmho_full.sql")
    args = parser.parse_args()

    db_user, db_name = get_db_env()
    steps = "3" if args.seed else "2"

    print(f"\n{'='*50}")
    print("  SysMho — Database Setup")
    print(f"  Target: {db_name} (user: {db_user})")
    print(f"{'='*50}\n")

    # Step 1: Wait for container
    print(f"[1/{steps}] Checking Docker container...")
    wait_for_container()

    # Step 2 (if --seed): Load seed data BEFORE schema so the dump's
    # CREATE TABLE statements succeed on the empty database. Schema and
    # migrations applied afterward are fully idempotent (IF NOT EXISTS).
    if args.seed:
        load_seed_data(db_user, db_name, step=2, total=steps)

    # Step N: Apply schema + migrations (idempotent — safe after seed or standalone)
    schema_step = "3" if args.seed else "2"
    print(f"\n[{schema_step}/{steps}] Applying schema and migrations...")
    apply_sql_file(SCHEMA_FILE, db_user, db_name, label="schema.sql")

    for migration in get_sorted_migrations():
        apply_sql_file(migration, db_user, db_name)

    # Summary
    verify_tables(db_user, db_name)
    print(f"\n  Setup complete.\n")


if __name__ == "__main__":
    main()
