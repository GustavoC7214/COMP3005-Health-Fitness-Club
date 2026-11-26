"""Optional PostgreSQL single-user smoke check; NOT an ORM connection test.

Set PG_SINGLE_BIN to postgres (with initdb beside it). This runs PostgreSQL
without opening a socket, useful in restricted environments. Normal users
should run the full TEST_DATABASE_URL suite instead.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models.member import FitnessGoal, HealthMetric, Member


def test_postgresql_single_user_schema_and_view(tmp_path):
    executable = os.getenv("PG_SINGLE_BIN")
    if not executable:
        pytest.skip("Optional socket-free SQL smoke test: set PG_SINGLE_BIN.")
    executable = Path(executable)
    data = tmp_path / "pgdata"
    initialized = subprocess.run(
        [
            str(executable.with_name("initdb")),
            "-D",
            str(data),
            "--no-locale",
            "--encoding=UTF8",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert initialized.returncode == 0, initialized.stderr
    dialect = postgresql.dialect()
    tables = [Member.__table__, FitnessGoal.__table__, HealthMetric.__table__]
    statements = ["SET TIME ZONE 'UTC';", "BEGIN;"]
    for model_table in tables:
        statements.append(str(CreateTable(model_table).compile(dialect=dialect)) + ";")
        statements.extend(
            str(CreateIndex(index).compile(dialect=dialect)) + ";"
            for index in model_table.indexes
        )
    sql_path = Path(__file__).resolve().parents[1] / "sql" / "views.sql"
    view = "\n".join(
        line
        for line in sql_path.read_text().splitlines()
        if not line.lstrip().startswith("--")
    )
    statements.extend([view, view])  # repeat installation must preserve the contract
    statements.extend(
        [
            "INSERT INTO members (first_name,last_name,email,date_of_birth) VALUES ('Demo','One','one@example.com','2000-01-01'),('Empty','Two','two@example.com','2000-01-01');",
            "INSERT INTO health_metrics (member_id,recorded_at,weight_kg,height_cm,heart_rate_bpm) VALUES (1,'2020-01-01T00:00:00Z',80,175,70),(1,'2020-01-02T00:00:00Z',78,NULL,NULL),(1,'2020-01-02T00:00:00Z',NULL,NULL,65);",
            "INSERT INTO fitness_goals (member_id,target_weight_kg,baseline_weight_kg) VALUES (1,75,80);",
            "UPDATE members SET first_name='Updated' WHERE member_id=1;",
            """DO $$ BEGIN
            IF (SELECT count(*) FROM health_metrics WHERE member_id=1) <> 3 THEN RAISE EXCEPTION 'history lost'; END IF;
            IF (SELECT weight_kg FROM health_metrics WHERE metric_id=1) <> 80 THEN RAISE EXCEPTION 'old metric changed'; END IF;
            IF (SELECT latest_metric_id FROM member_dashboard WHERE member_id=1) <> 3 THEN RAISE EXCEPTION 'latest tie order wrong'; END IF;
            IF (SELECT latest_weight_kg FROM member_dashboard WHERE member_id=1) <> 78 THEN RAISE EXCEPTION 'latest weight wrong'; END IF;
            IF (SELECT active_goal_count FROM member_dashboard WHERE member_id=1) <> 1 THEN RAISE EXCEPTION 'goal count wrong'; END IF;
            IF NOT EXISTS (SELECT 1 FROM member_dashboard WHERE member_id=2 AND latest_metric_id IS NULL AND active_goal_count=0) THEN RAISE EXCEPTION 'empty member lost'; END IF;
            BEGIN
                INSERT INTO members (first_name,last_name,email,date_of_birth) VALUES ('X','Y','one@example.com','2000-01-01');
                RAISE EXCEPTION 'duplicate accepted';
            EXCEPTION WHEN unique_violation THEN NULL; END;
            BEGIN
                INSERT INTO health_metrics (member_id,weight_kg) VALUES (1,-1);
                RAISE EXCEPTION 'bad weight accepted';
            EXCEPTION WHEN check_violation THEN NULL; END;
            BEGIN
                INSERT INTO health_metrics (member_id) VALUES (1);
                RAISE EXCEPTION 'empty metric accepted';
            EXCEPTION WHEN check_violation THEN NULL; END;
            BEGIN
                INSERT INTO health_metrics (member_id,weight_kg) VALUES (999,70);
                RAISE EXCEPTION 'orphan accepted';
            EXCEPTION WHEN foreign_key_violation THEN NULL; END;
            BEGIN
                INSERT INTO members (first_name,last_name,email,date_of_birth) VALUES ('X','Y','UPPER@example.com','2000-01-01');
                RAISE EXCEPTION 'uncanonical email accepted';
            EXCEPTION WHEN check_violation THEN NULL; END;
        END $$;""",
            "ROLLBACK;",
            "SELECT 'member1_sql_smoke_passed';",
        ]
    )
    # In single-user mode a newline ends an input command. Keep each complete
    # statement (including DO blocks) on one line.
    payload = (
        "\n".join(" ".join(statement.splitlines()) for statement in statements) + "\n"
    )
    checked = subprocess.run(
        [str(executable), "--single", "-D", str(data), "postgres"],
        check=False,
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = checked.stdout + checked.stderr
    assert checked.returncode == 0 and not re.search(
        r"\b(ERROR|FATAL|PANIC):", output
    ), output
    assert "member1_sql_smoke_passed" in output
