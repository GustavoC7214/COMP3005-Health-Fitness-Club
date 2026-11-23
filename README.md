# COMP3005-Health-Fitness-Club

## Member 1: Member Management & Health Tracking

This branch implements registration, profile/weight-goal management, append-only
health history, and the independent member dashboard. It uses the shared SQLAlchemy
Base, engine, and session manager already on `develop`. All existing paths are
retained. Trainer and Admin implementations are owned by the other team members.

Class attendance is implemented through `GroupClass` and `ClassAttendance` ORM
entities. The default dashboard reader counts distinct, attended classes that ended
before the query time, excluding cancelled classes. New members receive an actual
database count of zero. See `docs/member1_attendance.md` for data entry and mapping.
PT dashboard queries retain the existing Member 2 adapter: its actual model/table
and timestamp convention are required. See `docs/member1_integration.md`.

### Setup (Python 3.11+, PostgreSQL 16 or compatible)

From the project root, create a virtual environment and install dependencies:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux instead:
# source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a database using pgAdmin or PostgreSQL's `createdb` utility:

```bash
createdb -U postgres health_fitness_club
```

Copy `.env.example` to `.env` and fill in the existing `DB_HOST`, `DB_PORT`,
`DB_NAME`, `DB_USER`, and `DB_PASSWORD` settings. Never commit `.env`.

```bash
python main.py --init-db
python main.py
```

The initializer creates registered tables through `Base.metadata.create_all()`
and then installs `sql/views.sql`. It does not erase data. `create_all()` is not
a migration system: reconcile existing table definitions before using an older
database. Use a fresh development database for first setup.

Optional demonstration data, inserted through the ORM and committed to PostgreSQL:

```bash
python main.py --seed-demo
```

This explicitly creates `member1.demo@example.com`, two historical measurements,
and one weight goal if the email is absent. It also persists four group-class
fixtures: two attended, one absent, and one future registration. The demo member
therefore shows 2 past classes; a new member shows 0. Re-running the seed adds no
duplicate attendance. It never supplies fallback dashboard values. Fresh runs use
your own registrations and measurements normally.

### Four member operations

| Main menu | Functionality | Failure/edge cases |
|---|---|---|
| 1. User Registration | Name, normalized unique email, DOB, optional gender/phone | Duplicate email, blank name, invalid email, future DOB |
| 2. Profile Management | Update profile; create/update/list weight goals | Missing member, another member's goal, invalid weight/date/status |
| 3. Health History | Add timestamped weight/height/heart rate; list newest first | Empty measurement, invalid value/timestamp, empty history |
| 4. Member Dashboard | Latest observation, active goals/progress, real past-attendance count; PT read adapter | Empty member data, absent/cancelled/future classes excluded; missing PT integration explicitly reported |

Units: kilograms, centimetres, beats per minute. Measurement timestamps must
include a timezone offset; blank means current UTC time. Equal timestamps are
ordered by `metric_id`. Partial observations are displayed as recorded. Goal
progress uses the latest non-null weight, which may come from an earlier row.

The CLI is a classroom member interface selected by ID, not an authentication
system. The final team's identity/role layer must pass an authorized member ID
to these services. No trainer or admin modification commands are included here.

### Testing

Run tests without PostgreSQL to check validation and CLI error handling:

```bash
python -m pytest -q tests
```

Persistence tests skip unless `TEST_DATABASE_URL` is explicitly configured.
To execute them, create a dedicated test database and use a PostgreSQL/psycopg URL:

```bash
createdb -U postgres health_fitness_club_test
```

Windows PowerShell:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/health_fitness_club_test'
python -m pytest -q tests/test_members.py tests/test_member_cli.py tests/test_member_validation.py tests/test_member_attendance.py
```

macOS/Linux:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/health_fitness_club_test'
python -m pytest -q tests/test_members.py tests/test_member_cli.py tests/test_member_validation.py tests/test_member_attendance.py
```

URL-encode special characters in the password. The test role needs CREATE SCHEMA
permission. Each test creates and drops a uniquely named schema in this dedicated
database; it does not use shared application tables. `TEST_DATABASE_URL` is read
from the process environment, not automatically from `.env`.

After merging the trainer branch, also run `tests/test_member_trainer_integration.py`.
Its test database needs `btree_gist`, matching the trainer module's requirements.
The fixture creates Member 1 tables only; the optional integration test installs
the actual trainer tables it needs. It never defines replacement trainer models.

The optional `tests/test_member_sql_smoke.py` and `tests/test_member_attendance_sql.py` can run with `PG_SINGLE_BIN` pointing
to a `postgres` executable with `initdb` beside it. This verifies generated DDL,
indexes, constraints, and the view in PostgreSQL single-user mode. It does not
verify SQLAlchemy connection/transaction behavior. See `docs/member1_verification.md`
for the exact checks executed in this workspace.

```bash
python -m ruff check app tests main.py
```

### Documentation and team submission

- `docs/Member1_ERD.pdf`: Member 1 diagram, mapping, and normalization contribution only.
- `docs/relational_mapping.md` and `docs/normalization.md`: editable report sections.
- `docs/assumptions.md`: data and behavior assumptions.
- `docs/member1_attendance.md`: attendance entities, query rules and ORM data entry.
- `docs/member1_integration.md`: contracts and merge coordination.
- `GITHUB_UPLOAD_FILES.txt`: exact files to upload from this archive.
- `docs/member1_handoff.md`: deliverables, changed files, and outstanding work.
- `docs/demo_outline.md`: concise Member 1 video walkthrough.

The team still needs a complete `docs/ERD.pdf`, at least 10 entities, 10
relationships, 12 application operations across all three roles, and a view,
trigger, and index. These five entities and four member operations are only the
Member 1 contribution. Add the final accessible video link here before submission;
the official assignment limits the full team demonstration to 15 minutes.
