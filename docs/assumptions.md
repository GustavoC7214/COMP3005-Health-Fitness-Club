# Member 1 assumptions

These assumptions apply only to Member Management & Health Tracking.

1. A member has one first name, last name, normalized email, date of birth, and
   creation timestamp. Gender is optional free text (including "Prefer not to
   say"); phone is optional contact text. No address or login system is invented.
2. Emails are trimmed and lowercased before storage. A database CHECK requires
   canonical storage and basic email shape; UNIQUE prevents concurrent duplicates.
   This is basic input validation, not email ownership verification.
3. Each goal belongs to exactly one member. A member can have zero or many goals,
   including multiple active goals. This implementation supports target body weight.
   Other goal types can be designed later; they are not represented by unused fields.
4. Goal status is active, completed, or abandoned. Reaching a target does not
   automatically change status; the member updates it. A target date is optional
   and cannot precede the UTC date of goal creation. An overdue goal remains active.
5. The starting weight is an optional snapshot of the latest known weight when
   the goal is created. It remains fixed when the target is edited. No starting
   measurement means percentage progress is unavailable; creating a new goal after
   recording weight establishes a baseline. The application never invents one.
6. Goal progress is `(current - baseline) / (target - baseline) * 100`, clamped to
   0-100%, supporting weight gain and weight loss. If baseline equals target,
   progress is 100% only when current equals target, otherwise 0%. This is a simple
   distance-to-target display, not a medical assessment.
7. A health observation contains at least one metric. Weight is in kg, height in
   cm, and heart rate in integer bpm. Engineering bounds are `(0,500]`, `(0,300]`,
   and `[1,300]`, respectively; decimals support two places. They are input bounds,
   not clinical thresholds. Adjust bounds with a coordinated model migration.
8. Health timestamps use PostgreSQL TIMESTAMPTZ. Input requires an offset and is
   normalized to UTC. Backdated observations are allowed; future timestamps are
   rejected by the member service. Every insert gets its own primary key. Ties
   use descending metric_id. No member service updates or deletes historical rows.
   Direct privileged SQL/ORM writes can still edit rows: this is service-level
   append-only behavior, not a database immutability trigger.
9. "Latest health metrics" means the newest observation, including its null fields;
   values from different observations are not silently merged. Goal progress uses
   the latest non-null weight independently. The view exposes that weight's timestamp.
10. A member may exist without health history or goals. Child rows must reference
    an existing member; deletion is RESTRICTed to protect history. No deletion
    operation is included in the assigned four functions.
11. Past class count means distinct classes actually attended whose end is before
    the query time. Registration or booking alone does not establish attendance.
    GroupClass and ClassAttendance now provide this data, using timezone-aware
    times, class cancellation status and explicit attendance status. A composite
    (member_id, class_id) primary key prevents duplicate counting. The default ORM
    query is installed for both service and CLI callers; an empty result is 0.
    Attendance imports are separate from the member menu; members cannot self-certify
    attendance. See member1_attendance.md for the complete supplemental schema.
12. Upcoming PT sessions are scheduled, belong to the selected member, and start
    strictly after the query time. Cancelled/completed/past/current sessions are
    excluded. Member 2's current branch stores naive timestamps; the team must
    establish their timezone before setting PT_SESSION_TIMEZONE for the adapter.
13. The classroom CLI selects a member by ID. Team-level login/authorization is
    not implemented here; the final role layer must enforce access before calling
    services. Trainer and Admin service implementations are outside this scope.
