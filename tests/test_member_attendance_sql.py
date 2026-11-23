"""Execute the actual compiled ORM attendance query in socket-free PostgreSQL."""

import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.members.member_queries import past_attended_class_count_statement
from app.models.member import Member
from app.models.member_attendance import ClassAttendance, GroupClass


def test_attendance_query_and_constraints_in_postgresql(tmp_path):
    executable = os.getenv("PG_SINGLE_BIN")
    if not executable:
        pytest.skip("Optional socket-free PostgreSQL check: set PG_SINGLE_BIN.")
    executable = Path(executable)
    data = tmp_path / "attendance_pg"
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
    statements = ["SET TIME ZONE 'UTC';", "BEGIN;"]
    for entity in (Member, GroupClass, ClassAttendance):
        statements.append(
            str(CreateTable(entity.__table__).compile(dialect=dialect)) + ";"
        )
        statements.extend(
            str(CreateIndex(i).compile(dialect=dialect)) + ";"
            for i in entity.__table__.indexes
        )
    statements += [
        "INSERT INTO members (first_name,last_name,email,date_of_birth) VALUES ('A','One','a@example.com','2000-01-01'),('B','Two','b@example.com','2000-01-01'),('C','Empty','c@example.com','2000-01-01');",
        """INSERT INTO group_classes (name,start_time,end_time,status) VALUES
        ('Attended 1','2020-01-01T10:00Z','2020-01-01T11:00Z','completed'),
        ('Attended 2','2020-01-02T10:00Z','2020-01-02T11:00Z','scheduled'),
        ('Only registered','2020-01-03T10:00Z','2020-01-03T11:00Z','completed'),
        ('Absent','2020-01-04T10:00Z','2020-01-04T11:00Z','completed'),
        ('Cancelled enrollment','2020-01-05T10:00Z','2020-01-05T11:00Z','completed'),
        ('Cancelled class','2020-01-06T10:00Z','2020-01-06T11:00Z','cancelled'),
        ('Future','2040-01-01T10:00Z','2040-01-01T11:00Z','scheduled'),
        ('At cutoff','2030-01-01T09:00Z','2030-01-01T10:00Z','scheduled'),
        ('Still running','2030-01-01T09:00Z','2030-01-01T11:00Z','scheduled'),
        ('Other member','2020-01-07T10:00Z','2020-01-07T11:00Z','completed');""",
        """INSERT INTO class_attendance(member_id,class_id,status) VALUES
        (1,1,'attended'),(1,2,'attended'),(1,3,'registered'),(1,4,'absent'),
        (1,5,'cancelled'),(1,6,'attended'),(1,7,'attended'),(1,8,'attended'),
        (1,9,'attended'),(2,10,'attended');""",
    ]
    cutoff = datetime(2030, 1, 1, 10, tzinfo=UTC)
    for member_id, expected in [(1, 2), (2, 1), (3, 0)]:
        query = str(
            past_attended_class_count_statement(member_id, cutoff).compile(
                dialect=dialect, compile_kwargs={"literal_binds": True}
            )
        )
        statements.append(
            f"DO $$ BEGIN IF ({query}) <> {expected} THEN RAISE EXCEPTION 'wrong attendance count for member {member_id}'; END IF; END $$;"
        )
    statements += [
        """DO $$ BEGIN
        BEGIN INSERT INTO class_attendance VALUES (1,1,'attended',now()); RAISE EXCEPTION 'duplicate accepted'; EXCEPTION WHEN unique_violation THEN NULL; END;
        BEGIN INSERT INTO class_attendance VALUES (999,1,'attended',now()); RAISE EXCEPTION 'orphan member accepted'; EXCEPTION WHEN foreign_key_violation THEN NULL; END;
        BEGIN INSERT INTO class_attendance VALUES (1,999,'attended',now()); RAISE EXCEPTION 'orphan class accepted'; EXCEPTION WHEN foreign_key_violation THEN NULL; END;
        BEGIN INSERT INTO class_attendance VALUES (3,1,'invalid',now()); RAISE EXCEPTION 'bad attendance status'; EXCEPTION WHEN check_violation THEN NULL; END;
        BEGIN INSERT INTO group_classes(name,start_time,end_time) VALUES ('Bad',now(),now()); RAISE EXCEPTION 'invalid time'; EXCEPTION WHEN check_violation THEN NULL; END;
        BEGIN DELETE FROM members WHERE member_id=1; RAISE EXCEPTION 'history member deleted'; EXCEPTION WHEN foreign_key_violation THEN NULL; END;
        BEGIN DELETE FROM group_classes WHERE class_id=1; RAISE EXCEPTION 'history class deleted'; EXCEPTION WHEN foreign_key_violation THEN NULL; END;
        END $$;""",
        "ROLLBACK;",
        "SELECT 'member1_attendance_sql_passed';",
    ]
    checked = subprocess.run(
        [str(executable), "--single", "-D", str(data), "postgres"],
        input="\n".join(" ".join(s.splitlines()) for s in statements) + "\n",
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = checked.stdout + checked.stderr
    assert checked.returncode == 0 and not re.search(
        r"\b(ERROR|FATAL|PANIC):", output
    ), output
    assert "member1_attendance_sql_passed" in output
