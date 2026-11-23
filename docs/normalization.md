# Member 1 normalization and ORM contribution

## Functional dependencies

| Relation | Candidate key(s) | Non-key facts determined by the key |
|---|---|---|
| members | member_id; email | first_name, last_name, date_of_birth, gender, phone, created_at |
| fitness_goals | goal_id | member_id, target_weight_kg, baseline_weight_kg, target_date, status, created_at, updated_at |
| health_metrics | metric_id | member_id, recorded_at, weight_kg, height_cm, heart_rate_bpm |

Email is an alternate candidate key; no uniqueness is assumed for names, phone,
dates, or measurement timestamps. Several records can share an observation time.

**1NF:** Each row describes one member, goal, or timestamped observation, using
atomic values. Goals and health histories are not lists stored inside members;
there are no repeating columns such as weight1/weight2/weight3.

**2NF:** The candidate keys are single attributes. Every non-key attribute depends
on the whole key, so no partial key dependency exists.

**3NF:** No stated non-key attribute determines another non-key attribute. Member
contact data is stored only in members. Child tables carry the member key rather
than copied name/email values. Age, BMI, current weight, active-goal totals, and
progress percentage are not stored in members. They would become stale derived
data. The starting weight is a goal-specific historical snapshot fixed at creation,
not the member's current weight; it is allowed to be null and is determined by
goal_id. Active status is explicitly user-managed, not inferred from a date or weight.

These relations meet 3NF under the documented dependencies. The complete team's
other relations require their own normalization analysis.

## ORM usage (report contribution)

Member, FitnessGoal, and HealthMetric map to PostgreSQL tables through the team's
existing `app.database.base.Base`. `Mapped` columns define types, primary/foreign
keys, nullability, uniqueness, checks, and indexes. Bidirectional one-to-many
relationships allow `member.fitness_goals` and `member.health_metrics` navigation.
They use SQLAlchemy's normal lazy loading; the dashboard uses targeted ORM queries
for a single member instead of loading every historical observation.

Registration and metric recording use `Session.add()` and `Session.flush()`;
profile/goal updates assign validated mapped attributes. Retrieval uses
`Session.get()` or ORM `select(...)`. The existing `get_db_session()` context
commits once on success and rolls back on failure. Services never create another
engine, Base, or session factory. The only application exception to ORM entity
operations is installation/querying of the required PostgreSQL view, using raw
view DDL and a SQLAlchemy Core selectable. There are no direct psycopg CRUD queries.

```python
with get_db_session() as session:
    member = register_member(
        session, first_name="Demo", last_name="Member",
        email="demo@example.com", date_of_birth="2000-01-01",
    )
    record_health_metric(session, member.member_id, weight_kg="80")
    goal = create_fitness_goal(session, member.member_id, target_weight_kg="75")
```

The full ORM bonus depends on the complete team's ORM use, report, and demo.
This module supports those criteria but does not establish team-wide qualification.

## Attendance extension (23 November 2026)

GroupClass: class_id -> name, start_time, end_time, status.
ClassAttendance: (member_id, class_id) -> status, recorded_at.
Both relations use atomic values. ClassAttendance's non-key facts describe the
whole member/class pair; class dates and member names are not duplicated there.
There are no stated non-key-to-non-key dependencies, so both additions meet 3NF.
The two required foreign keys map Member 1:N ClassAttendance and GroupClass
1:N ClassAttendance, resolving the member/class many-to-many relationship.
The dashboard count remains derived. The original normalization analysis above
is unchanged.
