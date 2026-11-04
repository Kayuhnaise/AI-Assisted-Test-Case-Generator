
"""PostgreSQL execution utilities for DB-TestGen R2."""

import os
from contextlib import contextmanager

import psycopg


@contextmanager
def postgres_test_connection():
    """Provide a PostgreSQL connection that always rolls back."""

    database_url = os.getenv("DBTESTGEN_POSTGRES_URL")

    if not database_url:
        raise RuntimeError(
            "DBTESTGEN_POSTGRES_URL is not configured"
        )

    connection = psycopg.connect(
        database_url,
        autocommit=False,
        connect_timeout=5,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SET LOCAL statement_timeout = '5s'"
            )
            cursor.execute(
                "SET LOCAL lock_timeout = '2s'"
            )
            cursor.execute(
                "SET LOCAL search_path = dbtestgen_sandbox"
            )

        yield connection

    finally:
        connection.rollback()
        connection.close()
