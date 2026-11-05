
import pytest

from app.dbms_postgres_executor import postgres_test_connection


def test_postgres_transaction_rolls_back():
    with postgres_test_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE dbtestgen_rollback_check "
                "(id INTEGER PRIMARY KEY)"
            )
            cursor.execute(
                "INSERT INTO dbtestgen_rollback_check VALUES (1)"
            )
            cursor.execute(
                "SELECT COUNT(*) FROM dbtestgen_rollback_check"
            )
            assert cursor.fetchone()[0] == 1

    # The table creation should have been rolled back.
    with postgres_test_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass("
                "'dbtestgen_sandbox.dbtestgen_rollback_check')"
            )
            assert cursor.fetchone()[0] is None
