# Member 1 integration contract

## Repository baseline and scope

Inspected on 2026-11-17. Local `feature/member1` starts at `develop` commit
`2170820636697c3e15491440b159cf7f1e592a2e`.

| Inspected branch | Head | Findings |
|---|---|---|
| develop | 2170820 | Existing Base, connection/session manager, init_db, app/models placeholders |
| feature/database-setup | 1c4feca | Foundation already merged into develop |
| feature/trainers | ecb2798 | Trainer, TrainerAvailability, PTSession; expected members.member_id and first_name/last_name |
| main | c2ac465 | Original skeleton; untouched |

The three original Member 1 entities remain in `app/models/member.py`. The
attendance addition lives in `app/models/member_attendance.py`; all five use the
established Base. No existing member entity or transaction architecture changed. `connection.py`, `base.py`,
requirements, every Trainer/Admin file, and the original directory names are unchanged.

The connected GitHub account reported pull=true, push=false. Work is local and
uncommitted. Nothing was pushed, no PR opened, and neither main nor develop was
modified. The source archive can be copied into a local feature/member1 checkout.

## Stable interfaces

```python
from app.database.base import Base
from app.database.connection import get_db_session
from app.models.member import Member, FitnessGoal, HealthMetric
from app.members.member_service import (
    get_member, get_fitness_goals, get_health_history, get_member_dashboard,
)
```

`members.member_id` is INTEGER. Names are `first_name` and `last_name`, matching
the trainer branch's existing lookup. Other modules must import this model, not
redeclare the members table. `FitnessGoal.member_id` and `HealthMetric.member_id`
are mandatory foreign keys. All five models use the same Base metadata.

Services receive an existing Session, flush their writes, and do not commit.
Call them inside the shared `get_db_session()` context. If a caller catches an
IntegrityError/DuplicateEmailError, it must roll back before reusing that session.
The CLI does this through the existing context manager. Returned ORM objects
should be rendered while the session is open unless already loaded.

Member-specific write entry points: `register_member`, `update_profile`,
`create_fitness_goal`, `update_fitness_goal`, `record_health_metric`.
Goal updates filter on both member_id and goal_id. No historical edit/delete API.

## Dashboard dependencies

| Field | Current implementation | Integration action |
|---|---|---|
| Latest observation | Real member_dashboard view + ORM HealthMetric read | Complete independently |
| Goals/progress | ORM active-goal query + latest non-null DB weight | Complete independently |
| Past attended classes | Default ORM query against GroupClass/ClassAttendance; actual count including 0 | Complete; reuse these shared models or override the reader for another agreed schema |
| Upcoming PT sessions | Read adapter for actual Member 2 PTSession ORM model | Merge/register trainer models, create table, confirm timezone |

GroupClass (`group_classes`) and ClassAttendance (`class_attendance`) provide the
minimal shared data for this requirement. Attendance status must be `attended`,
class status must not be `cancelled`, and end_time must be strictly before as_of.
Names or registration alone do not establish attendance. The member menu only reads
this data. Database import helpers and the explicit demo seed populate it through ORM.

The working default is installed automatically:

```python
from app.members.member_queries import DashboardIntegrations, count_past_attended_classes

integrations = DashboardIntegrations()  # past_class_count already uses the real query
# After agreeing Member 2's convention, add pt_session_timezone="UTC" if appropriate.
```

The team can reuse these models. If a different shared class schema is chosen,
provide an equivalent `(session, member_id, as_of) -> int` reader through
`DashboardIntegrations(past_class_count=your_reader)`. Replace the underlying schema
with a reviewed migration; do not define duplicate tables with the same names on Base.
An explicit None disables this external-reader contract; it is never the default.
Callback errors propagate and are not hidden as zero.

The PT read adapter imports the existing `app.models.trainer.PTSession`, verifies
its table exists, and selects by member_id, status='scheduled', start_time > now.
It never writes sessions. The current trainer branch uses TIMESTAMP WITHOUT TIME
ZONE. Until its convention is confirmed, leave PT_SESSION_TIMEZONE unset and the
dashboard reports that requirement. Once confirmed, set an IANA name (e.g. UTC)
in the environment/.env. If the trainer model is changed to TIMESTAMPTZ, the
adapter reads aware timestamps directly. Ambiguous daylight-saving wall times
remain the trainer module's responsibility; prefer a shared UTC convention.
UTC works without an operating-system timezone database. On Windows, using another
IANA timezone may require `python -m pip install tzdata` in the environment.

## Merge coordination

1. `app/models/__init__.py` is edited on both branches. Keep Member/FitnessGoal/
   HealthMetric/GroupClass/ClassAttendance imports AND Trainer/TrainerAvailability/PTSession imports, and
   combine __all__. Do not replace one branch's registration with the other.
2. `app/database/init_db.py` is edited on both branches. Retain Member 2's
   btree_gist extension creation BEFORE metadata.create_all(), and retain Member 1's
   install_member_view(engine) AFTER table creation. Do not create a second engine.
3. Compose `run_member_cli()` and the teammate-owned menus in the final main.py.
   The current entry point only exposes Member 1 work; no Trainer/Admin code was
   copied from feature/trainers into this branch.
4. The view is intentionally limited to independent Member 1 data. Once final
   class/session models are agreed, either keep those reads in adapters or extend
   the same view with separately aggregated subqueries. Never join raw goals,
   measurements and enrollments together in a way that multiplies attendance counts.
5. The team's authentication/role layer must authorize member IDs before calling
   write services. Member 2 can use the read helpers for assigned-member lookup,
   subject to its own authorization rules. This branch does not grant trainer writes.
6. Populate the remaining ORM tables through their owner modules, add the team's
   trigger, combine all ER sections into docs/ERD.pdf, and run complete integration
   tests and the demonstration. No claim of complete team compliance is made here.

No team confirmation was needed to place models or select primary keys: those
contracts already exist. Attendance is now independent of teammate code. The remaining shared decisions
are naive PT timezone, final menu/auth composition, and merge overlap.
