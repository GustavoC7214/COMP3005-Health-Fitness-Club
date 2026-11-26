# Member 1 attendance completion

Completed 23 November 2026. The existing registration/profile/goal/health-history
implementations and SQL view are retained. No Trainer/Admin files are modified.

## Schema and mapping

| Entity/table | Columns | Keys and constraints |
|---|---|---|
| GroupClass / group_classes | class_id INTEGER; name VARCHAR(150); start_time/end_time TIMESTAMPTZ; status VARCHAR(20) | PK class_id; all fields required; nonblank name; end > start; status scheduled/completed/cancelled |
| ClassAttendance / class_attendance | member_id INTEGER; class_id INTEGER; status VARCHAR(20); recorded_at TIMESTAMPTZ | Composite PK (member_id,class_id); both required FKs with ON DELETE RESTRICT; status registered/attended/absent/cancelled; all fields required |

Member 1:N ClassAttendance and GroupClass 1:N ClassAttendance resolve the
member/class M:N relationship. A member or class can have zero attendance rows;
each attendance row must have exactly one member and one class. The composite PK
prevents two rows for one member/class pair. Status updates change that pair rather
than create duplicate participation. This does not modify health history.

GroupClass.class_id determines its name/times/status. The whole ClassAttendance
composite key determines attendance status and recorded_at. Class properties and
member profiles are not duplicated in attendance; both additions meet 3NF under
these dependencies. Indexes cover (member_id,status) and class_id.

## Actual default dashboard query

`app/members/member_queries.py` contains the ORM statement and reader. Both
`get_member_dashboard(session, member_id)` and the existing menu install it by
means of the default DashboardIntegrations value. No caller configuration is needed.

Equivalent SQL (parameters remain bound in the actual ORM call):

```sql
SELECT count(DISTINCT a.class_id)
FROM class_attendance AS a
JOIN group_classes AS c ON c.class_id = a.class_id
WHERE a.member_id = :member_id
  AND a.status = 'attended'
  AND c.status <> 'cancelled'
  AND c.end_time < :as_of;
```

The count is always derived from PostgreSQL, not a constant. Registered, absent,
cancelled, future, still-running and other members' records do not contribute.
An ended class can count even if its class status was not manually changed from
scheduled to completed: actual attendance and end_time establish participation.
At the exact end-time cutoff it does not yet count. Empty history is 0.
The query does not join health metrics/goals, so those histories cannot inflate it.

## Install and demonstrate

Use the same environment and PostgreSQL setup in README.md. From the project root:

```bash
python main.py --init-db
python main.py --seed-demo
python main.py
```

The existing initializer creates the two new tables through registered ORM models.
For an existing database with the original three member tables, re-run --init-db;
those tables and their rows are not replaced. An unrelated pre-existing table with
the same name and a different shape requires a reviewed schema migration.

The seed prints the demo member ID. Choose menu 4 and enter it: past attended
classes = 2, from real persisted Yoga/Strength attendance. The absent Mobility
class and future Upcoming registration are excluded. Re-running the seed does not
add duplicate attendance. A newly registered member shows 0. The seed only runs
when explicitly requested and does not populate other users' attendance.

## ORM data imports / future integration

Course and attendance inputs are separate from the member-facing menu. The member
cannot certify attendance or manage classes through that interface. Authorized
import/admin code may call the reusable helpers, inside its own transaction:

```python
from datetime import UTC, datetime, timedelta
from app.database.connection import get_db_session
from app.database.attendance_setup import create_group_class, set_class_attendance

# Substitute an existing member ID. These are authorized data import examples.
with get_db_session() as session:
    start = datetime.now(UTC) - timedelta(days=1)
    group_class = create_group_class(
        session,
        name="Yoga",
        start_time=start,
        end_time=start + timedelta(hours=1),
        status="completed",
    )
    set_class_attendance(
        session, member_id=1, class_id=group_class.class_id, status="attended"
    )
```

Helpers validate IDs, required text, offset-aware times, positive class duration
and statuses. Marking future/cancelled classes attended is rejected. FK/PK/CHECK
constraints independently protect the database. Readers also filter inconsistent
imports, such as an attended row for a subsequently cancelled class.

Other modules may reuse GroupClass/ClassAttendance and extend their schema in a
coordinated migration. If the team chooses another schema, the existing optional
`DashboardIntegrations(past_class_count=your_real_query)` hook is retained. Do not
register a second table with the same name on the shared Base.

PT scheduling remains with Member 2. Its existing read adapter is preserved and
requires its real model/table plus the agreed timezone for naive timestamps.
This change does not manufacture PT data or add Trainer/Admin operations.
