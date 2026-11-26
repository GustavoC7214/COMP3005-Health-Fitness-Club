# Trainer Management Module

## 1. Overview

The Trainer Management Module is responsible for trainer availability, personal training session scheduling, trainer schedules, and assigned-member lookup within the Health and Fitness Club Management System.

The module uses Python, SQLAlchemy ORM, and PostgreSQL. Trainer operations are accessible through the application's main command-line interface.

## 2. Database Entities

### Trainer

Stores trainer information.

- `trainer_id` — Primary key
- `first_name` — Trainer's first name
- `last_name` — Trainer's last name
- `email` — Unique email address
- `specialization` — Area of expertise

### TrainerAvailability

Stores time intervals during which trainers are available.

- `availability_id` — Primary key
- `trainer_id` — Foreign key referencing Trainer
- `start_time` — Availability start
- `end_time` — Availability end

### PTSession

Stores personal training appointments.

- `session_id` — Primary key
- `trainer_id` — Foreign key referencing Trainer
- `member_id` — Foreign key referencing Member
- `start_time` — Appointment start
- `end_time` — Appointment end
- `status` — Scheduled, completed, or cancelled

## 3. Entity Relationships

- One trainer can define multiple availability intervals.
- One trainer can conduct multiple personal training sessions.
- One member can book multiple personal training sessions.
- Each personal training session belongs to one trainer and one member.

## 4. Implemented Operations

### Trainer Availability

- Add trainer availability.
- View trainer availability.
- Reject overlapping availability intervals.
- Reject invalid time intervals.
- Allow adjacent availability intervals.

### Personal Training Scheduling

- Book a personal training session.
- Reschedule an existing scheduled session.
- Cancel a scheduled session.
- Prevent overlapping scheduled sessions for the same trainer or member.
- Reject bookings outside the trainer's available hours.
- Preserve cancelled booking records.
- Allow adjacent appointments.

### Trainer Schedule

- Retrieve scheduled personal training sessions.
- Display appointments chronologically.
- Represent PT sessions and group classes using a shared schedule-entry structure.
- Correctly sort timezone-aware and timezone-naive timestamps.
- Display scheduling timestamps explicitly in UTC.

Group-class database retrieval remains pending administrative-module integration.

### Assigned-Member Lookup

- Retrieve members assigned to a trainer through scheduled PT sessions.
- Search assigned members by first name, last name, or full name.
- Perform case-insensitive searches.
- Treat SQL wildcard characters as literal search characters.
- Prevent duplicate members in search results.
- Retrieve the latest recorded health metric.
- Retrieve current active fitness goals.
- Provide read-only access to member health information.
- Restrict query results to members assigned to the selected trainer.

Assignment filtering is based on the selected trainer ID. The CLI does not independently authenticate trainer identities.

### Member Dashboard Integration

Scheduled PT sessions are accessible through the member dashboard.

The dashboard displays upcoming appointments belonging to the selected member and excludes cancelled, completed, past, and unrelated appointments.

The integration uses the shared SQLAlchemy ORM models rather than duplicate member or trainer entities.

## 5. Database Constraints

The module uses PostgreSQL and SQLAlchemy constraints to maintain scheduling integrity.

- Primary keys uniquely identify records.
- Foreign keys maintain trainer and member references.
- Check constraints enforce valid time intervals.
- Session status is restricted to supported values.
- PostgreSQL exclusion constraints prevent overlapping trainer availability.
- Exclusion constraints prevent overlapping scheduled PT sessions for trainers and members.
- Indexes support availability and session lookup by trainer, member, and start time.

The PostgreSQL `btree_gist` extension is required for the exclusion constraints.

## 6. Timestamp Convention

Trainer availability and personal training session timestamps use UTC.

The existing PostgreSQL timestamp columns store naive UTC values without timezone information.

The scheduling service interprets naive datetime inputs as UTC and converts timezone-aware inputs to UTC before removing timezone information for database storage.

Timestamp normalization occurs before interval validation, availability checks, conflict detection, and database insertion or updates.

The trainer CLI explicitly requests UTC input and labels scheduling output as UTC.

The shared schedule representation supports chronological comparisons between naive UTC timestamps and timezone-aware timestamps.

The member dashboard requires the following environment configuration:

```dotenv
PT_SESSION_TIMEZONE=UTC
```

This setting is included in `.env.example`.

Existing database timestamps are not automatically converted. Any historical records created using another timezone convention require separate migration or correction.

## 7. Implementation Structure

- `app/models/trainer.py` — SQLAlchemy ORM models.
- `app/trainers/trainer_service.py` — Scheduling and member-lookup business logic.
- `app/trainers/trainer_cli.py` — Trainer command-line interface.
- `app/trainers/schedule.py` — Shared schedule representation and timestamp normalization.
- `app/database/init_db.py` — Shared ORM schema initialization.
- `main.py` — Main application and role-menu navigation.
- `tests/test_trainers.py` — PostgreSQL-backed database and service tests.
- `tests/test_trainer_cli.py` — CLI tests.
- `tests/test_trainer_schedule.py` — Schedule and timestamp tests.
- `tests/test_member_trainer_integration.py` — Member dashboard integration tests.

## 8. Testing

The trainer module includes automated tests covering:

- ORM models, relationships, constraints, and indexes.
- Availability creation and overlap prevention.
- PT booking, rescheduling, and cancellation.
- Trainer and member scheduling conflicts.
- Assigned-member search and result isolation.
- Latest health metrics and active fitness goals.
- CLI input validation and output.
- Mixed-timezone schedule ordering.
- UTC timestamp normalization.
- PostgreSQL timestamp persistence.
- Conflict detection across different timezone representations.

PostgreSQL-backed tests use isolated schemas to avoid modifying application data.

Set `TEST_DATABASE_URL` to a dedicated PostgreSQL test database before running the tests.

```bash
python -m pytest tests/test_trainers.py \
    tests/test_trainer_cli.py \
    tests/test_trainer_schedule.py -v
```

Run the complete project test suite with:

```bash
python -m pytest tests/ -q -rs
```

Code quality is checked using Ruff:

```bash
python -m ruff check .
python -m ruff format --check .
```

## 9. Running the Application

Configure PostgreSQL connection settings in `.env` and initialize the shared database:

```bash
python main.py --init-db
```

Launch the application:

```bash
python main.py
```

Select option 2 to access Trainer Management.

The trainer menu provides seven operations:

1. Add trainer availability.
2. View trainer availability.
3. Book personal training session.
4. Reschedule personal training session.
5. Cancel personal training session.
6. View trainer schedule.
7. View assigned members.

Option 0 returns to the main application menu.

## 10. Remaining Integration Work

The following tasks require coordination with the administrative-module developer:

1. Retrieve group fitness classes assigned to a trainer.
2. Include retrieved group classes in the combined trainer schedule.
3. Implement room assignment for personal training sessions.
4. Prevent room conflicts between personal training sessions and group classes.
5. Coordinate scheduling constraints across personal training sessions and group classes.
6. Confirm the shared UTC timestamp convention.
7. Perform final integration testing after the administrative module is merged.

## 11. Current Status

The trainer-management functionality and member-module integration are implemented.

Live PostgreSQL verification has confirmed availability creation, PT booking, trainer schedule retrieval, assigned-member lookup, health metric retrieval, fitness-goal retrieval, and member dashboard integration.

Administrative scheduling and room integration remain pending.

The shared schedule representation and timestamp normalization utilities are prepared for administrative-module integration.