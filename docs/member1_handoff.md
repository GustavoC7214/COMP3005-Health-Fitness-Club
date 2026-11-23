# Member 1 implementation handoff

Updated 23 November 2026. Base: develop
2170820636697c3e15491440b159cf7f1e592a2e, plus the supplied Member 1 implementation.
No GitHub commits, pushes, pull requests or merges were performed.

| Requirement | Current implementation |
|---|---|
| Registration | Original ORM implementation, canonical unique email, validation/duplicate handling |
| Profile / fitness goals | Original personal-data and weight-goal management retained |
| Health history | Original timestamped append-only member service retained |
| Latest stats / goals / progress | Original PostgreSQL view and ORM queries retained |
| Past class count | Completed: real default ORM query, GroupClass/ClassAttendance, no teammate dependency |
| Upcoming PT sessions | Original read adapter for Member 2 model/table/timezone retained |
| Documentation | Original core ER model updated with page 4 attendance extension; mapping/3NF and demo instructions updated |
| Tests | 53 passed, 66 connection-dependent tests skipped; exact limits in member1_verification.md |

## Apply / run

The archive contains a complete source tree. GITHUB_UPLOAD_FILES.txt distinguishes
all changes relative to current develop from the smaller set changed in this
attendance follow-up. Create feature/member1 from develop and copy only the listed
paths, combining any newer shared-file work. Submit a PR into develop as agreed by
the group. Do not overwrite teammate changes with an older complete snapshot.

```bash
python -m pip install -r requirements.txt
python main.py --init-db
python main.py --seed-demo
python main.py
```

The optional seed now persists two attended classes, one absent class and one future
registration for the demo member only. Dashboard shows 2 for that member and 0 for
a new member. README.md documents ordinary use without seeding.

## This follow-up's scope

The original Member/FitnessGoal/HealthMetric model, member_service.py, member_cli.py,
validators, SQL view, connection.py/Base, main.py and all Trainer/Admin files are
retained byte-for-byte. New attendance models and ORM import helpers are registered
on the same Base. DashboardIntegrations now has the actual attendance reader as its
default, so existing service/CLI calls need no changes. Only the demo initializer,
model imports, affected test fixtures/assertions, and related documentation changed.
No attendance-writing commands were added to the member menu.

## Shared integration still outside this follow-up

1. Preserve all five Member 1 model imports AND Member 2's Trainer/Availability/PT
   imports when combining app/models/__init__.py.
2. Preserve trainer btree_gist initialization before create_all, and the member
   view installation after it in app/database/init_db.py.
3. The original upcoming-PT adapter requires the real trainer models/tables and
   confirmed naive-timestamp convention. Set PT_SESSION_TIMEZONE only once agreed.
4. Reuse the attendance models or deliberately migrate/adapt a different class
   schema; the override reader interface remains supported.
5. Team-level identity, other role operations, complete team ERD/report and team
   video remain with the group. This archive covers Member 1, not the whole team.

## Demonstration

Show registration and duplicate rejection; update a profile/goal; add two health
measurements and show preserved history; show latest stats/40% goal progress and
past attendance 2 for the seeded demo member; show 0 for a new member. Point to
member_queries.py's real class/attendance join, model PK/FK/CHECK declarations and
ORM data-entry helpers. Do not present skipped tests as passed or unavailable PT
rows as an integrated PT feature. docs/demo_outline.md provides the original flow.
