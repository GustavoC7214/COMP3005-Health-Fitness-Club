# Member 1 demonstration (about 3.5-4 minutes of the 15-minute team video)

Use a fresh development database. Run `python main.py --init-db`, then
`python main.py`. For a predictable sample without typing every field, the optional
`--seed-demo` command creates real PostgreSQL rows; do not present it as registration.

| Time | What to show | Suggested narration |
|---|---|---|
| 0:00-0:30 | Member1_ERD.pdf and app/models/member.py | "My role is Member Management and Health Tracking. A member has zero or many goals and health observations. Each child belongs to exactly one member through a non-null foreign key. The original member relations and the two attendance relations meet 3NF; this is our Member 1 contribution to the full team model." |
| 0:30-1:10 | Menu 1: register; repeat same email with different case; try invalid DOB/email | "Registration uses SQLAlchemy Session.add and flush. PostgreSQL enforces the unique canonical email, so duplicates are rejected even if requests arrive concurrently. Invalid input is reported and the menu continues." |
| 1:10-1:55 | Menu 2: change phone/name; menu 3: add 80 kg; menu 2: create 75 kg goal; update goal date/status as needed | "Profile and goal updates change mapped ORM objects in a transaction. A goal captures the starting weight available at creation. Goal updates are restricted to the selected member. A missing member ID or negative target is rejected." |
| 1:55-2:40 | Menu 3: add 78 kg; list history; try negative weight/empty metrics | "Every measurement is inserted with a timestamp and a new key. Earlier measurements remain unchanged. History orders by observation time and then key, so backdated entries do not become the latest record." |
| 2:40-3:20 | Menu 4: dashboard; show empty newly registered member; try nonexistent ID | "The PostgreSQL view identifies the latest observation and latest available weight. Active goals come from ORM queries; 80 to 78 toward 75 gives 40 percent progress. Members with no measurements or goals get an explicit empty state." |
| 3:20-4:00 | member_queries.py, shared session manager, test results | "Most database interactions use ORM operations. The required view is the limited SQL exception. The shared context commits successful writes and rolls back failures. These tests include duplicates, invalid input, persistence, history preservation, and dashboard edge cases." |

For attendance, run `python main.py --seed-demo` and show the printed demo member
ID in menu 4: its count is 2. Show a fresh member with count 0. Explain the absent
and future-registration fixtures are excluded; show the real ORM join/count query
in member_queries.py and the stored rows in PostgreSQL. Attendance imports are
not exposed as member self-service edits.
For the final PT integration demonstration, use future scheduled PT rows entered
by Member 2, plus cancelled/past rows excluded. The existing adapter needs the
real trainer model/table and agreed timestamp timezone. Show tests that actually
ran; do not describe skipped tests as passed.

Quick reproducible menu path for a fresh member (note its printed member ID):

1. Register `demo.video@example.com` with name and valid DOB.
2. Record 80 kg, 175 cm, 70 bpm using Health History -> Add.
3. Create a 75 kg goal using Profile Management -> Create weight goal.
4. Update name/phone, then try member ID 999999 to show graceful failure.
5. Add 78 kg and 68 bpm. List history: both observations remain.
6. Show the dashboard with 40% progress, then an empty member dashboard.
7. Re-register the same email and attempt a negative metric to demonstrate failures.

Backend files to point to: `app/models/member.py`, `member_service.py`,
`member_queries.py`, `app/database/connection.py`, and `sql/views.sql`.
The full team video must also show its other roles, complete ERD/mapping,
database population, interface navigation, and an accessible video link in README.
