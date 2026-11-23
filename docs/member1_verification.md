# Member 1 verification record

Updated 23 November 2026. Baseline: develop 2170820 and the provided Member 1 ZIP.

| Check | Executed result | Practical scope |
|---|---|---|
| Validation, CLI recovery and attendance reader/input checks | 51 passed | Existing checks plus default reader wiring, real scalar transport and rejected attendance/class inputs |
| PostgreSQL 16.2 single-user schema/view smoke | 1 passed | Original member DDL/indexes/view/constraints and historical measurements retained |
| PostgreSQL 16.2 single-user attendance smoke | 1 passed | Actual compiled ORM count SQL; selected-member isolation; 0 count; registered/absent/cancelled/future/running/exact-cutoff exclusions; duplicate/FK/CHECK/delete protection |
| PostgreSQL connection-dependent tests | 66 skipped | Includes 6 new attendance persistence/dashboard/seed cases; not passed or claimed executed |
| Ruff | Passed | app, tests and main.py |

The complete executed suite returned **53 passed, 66 skipped**. The two single-user
checks execute actual PostgreSQL SQL without opening server sockets; the attendance
check compiles the same SQLAlchemy statement used by the application.

The runtime denies socket creation, so a normal psycopg/PostgreSQL connection and
full ORM persistence/rollback/CLI run could not be exercised here. Do not equate
the SQL smoke checks with a passing connected end-to-end test. The packaged tests
are ready to execute against a dedicated local PostgreSQL test database.

Windows PowerShell (after creating health_fitness_club_test):

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/health_fitness_club_test'
python -m pytest -q -ra tests
python -m ruff check app tests main.py
```

URL-encode special characters in the password. Tests require CREATE SCHEMA and
use isolated schemas, not shared application tables. The two optional single-user
tests skip without PG_SINGLE_BIN. PT integration skips until Member 2's actual
models are merged. No attendance integration is skipped because of missing code.

The original Member/FitnessGoal/HealthMetric models, member_service.py,
member_cli.py, validators, shared connection/Base, SQL view and all Trainer/Admin
files are byte-identical to the supplied ZIP. Existing tests changed only where
the completed attendance feature replaces an unavailable result with a real count.
See GITHUB_UPLOAD_FILES.txt for exact upload and patch lists.
