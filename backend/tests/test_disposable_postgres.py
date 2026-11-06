import subprocess
from unittest.mock import patch

import pytest

from app.disposable_postgres import disposable_postgres


def test_disposable_postgres_creates_and_cleans_isolated_instance():
    port = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="127.0.0.1:49153\n",
        stderr="",
    )

    with (
        patch("app.disposable_postgres.shutil.which", return_value="/docker"),
        patch(
            "app.disposable_postgres._docker",
            side_effect=[
                subprocess.CompletedProcess([], 0, "network-id", ""),
                subprocess.CompletedProcess([], 0, "container-id", ""),
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 0, "", ""),
                port,
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 0, "", ""),
            ],
        ) as docker,
        patch(
            "app.disposable_postgres.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ),
    ):
        with disposable_postgres() as database_url:
            assert database_url.startswith(
                "postgresql://dbtestgen_runner:"
            )
            assert database_url.endswith("@127.0.0.1:49153/dbtestgen")

    commands = [item.args[0] for item in docker.call_args_list]
    assert commands[0][:2] == ["network", "create"]
    run_command = commands[1]
    assert "--network" in run_command
    assert "--memory" in run_command
    assert "--cpus" in run_command
    assert "--pids-limit" in run_command
    assert "127.0.0.1::5432" in run_command
    assert "--volume" not in run_command
    assert docker.call_args_list[2].kwargs["input_text"].find(
        "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION"
    ) >= 0
    assert commands[-2][:2] == ["rm", "--force"]
    assert commands[-1][:2] == ["network", "rm"]


def test_disposable_postgres_requires_docker_cli():
    with (
        patch("app.disposable_postgres.shutil.which", return_value=None),
        pytest.raises(RuntimeError, match="Docker CLI"),
    ):
        with disposable_postgres():
            pytest.fail("No container should be started")
