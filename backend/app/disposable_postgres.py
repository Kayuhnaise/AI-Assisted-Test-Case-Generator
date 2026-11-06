"""Short-lived disposable PostgreSQL containers for reviewed SQL."""

from __future__ import annotations

import secrets
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from typing import Generator
from urllib.parse import quote


POSTGRES_IMAGE = "postgres:17"
STARTUP_TIMEOUT_SECONDS = 45
RUNNER_ROLE = "dbtestgen_runner"
DATABASE_NAME = "dbtestgen"
SANDBOX_SCHEMA = "dbtestgen_sandbox"


def _docker(
    arguments: list[str],
    *,
    input_text: str | None = None,
    timeout: float = 15,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", *arguments],
        input=input_text,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Docker command failed: {detail}")
    return result


@contextmanager
def disposable_postgres() -> Generator[str, None, None]:
    """Yield a runner-only URL to a fresh PostgreSQL container.

    The container uses a private bridge, no host mounts, resource limits, and
    a localhost-only published port. The bridge may allow outbound traffic.
    Its database role lacks superuser and role/database privileges.
    """
    if shutil.which("docker") is None:
        raise RuntimeError("Docker CLI is required for PostgreSQL evaluation")

    suffix = uuid.uuid4().hex[:12]
    network_name = f"dbtestgen-{suffix}"
    container_name = f"dbtestgen-pg-{suffix}"
    admin_password = secrets.token_urlsafe(24)
    runner_password = secrets.token_urlsafe(24)
    network_created = False
    container_created = False

    try:
        _docker(["network", "create", network_name])
        network_created = True

        _docker([
            "run",
            "--detach",
            "--name",
            container_name,
            "--network",
            network_name,
            "--publish",
            "127.0.0.1::5432",
            "--memory",
            "1g",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            "--restart",
            "no",
            "--env",
            f"POSTGRES_PASSWORD={admin_password}",
            "--env",
            "POSTGRES_DB=postgres",
            POSTGRES_IMAGE,
        ], timeout=300)
        container_created = True

        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while True:
            probe = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    "5432",
                    "-U",
                    "postgres",
                    "-d",
                    "postgres",
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )
            if probe.returncode == 0:
                break
            if time.monotonic() >= deadline:
                detail = probe.stderr.strip() or probe.stdout.strip()
                raise RuntimeError(
                    "Disposable PostgreSQL container failed to become ready"
                    + (f": {detail}" if detail else "")
                )
            time.sleep(0.5)

        _docker(
            [
                "exec",
                "-i",
                container_name,
                "psql",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
            ],
            input_text=(
                f"CREATE ROLE {RUNNER_ROLE} LOGIN "
                f"PASSWORD '{runner_password}' NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION;\n"
            ),
        )
        _docker(
            [
                "exec",
                "-i",
                container_name,
                "psql",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
            ],
            input_text=(
                f"CREATE DATABASE {DATABASE_NAME} OWNER {RUNNER_ROLE};\n"
            ),
        )
        _docker(
            [
                "exec",
                "-i",
                container_name,
                "psql",
                "-U",
                RUNNER_ROLE,
                "-d",
                DATABASE_NAME,
                "-v",
                "ON_ERROR_STOP=1",
            ],
            input_text=(
                f"CREATE SCHEMA {SANDBOX_SCHEMA} "
                f"AUTHORIZATION {RUNNER_ROLE};\n"
            ),
        )

        port_result = _docker(
            ["port", container_name, "5432/tcp"]
        )
        port = port_result.stdout.strip().rsplit(":", maxsplit=1)[-1]
        if not port.isdecimal():
            raise RuntimeError(
                "Docker did not return a valid PostgreSQL host port"
            )

        yield (
            f"postgresql://{RUNNER_ROLE}:"
            f"{quote(runner_password, safe='')}@127.0.0.1:{port}/"
            f"{DATABASE_NAME}"
        )
    finally:
        try:
            if container_created:
                _docker(["rm", "--force", "--volumes", container_name])
        finally:
            if network_created:
                _docker(["network", "rm", network_name])
