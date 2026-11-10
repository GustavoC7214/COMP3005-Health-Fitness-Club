# Trainer Management Module

## 1. Overview

The Trainer Management Module is responsible for trainer availability, personal training session scheduling, and assigned-member lookup within the Health and Fitness Club Management System.

The module uses Python, SQLAlchemy ORM, and PostgreSQL. Trainer operations are accessible through a command-line interface.

## 2. Database Entities

### Trainer

Stores trainer information.

Attributes:
- `trainer_id` — Primary key
- `first_name` — Trainer's first name
- `last_name` — Trainer's last name
- `email` — Unique email address
- `specialization` — Area of expertise

### TrainerAvailability

Stores time intervals during which trainers are available.

Attributes:
- `availability_id` — Primary key
- `trainer_id` — Foreign key referencing Trainer
- `start_time` — Availability start
- `end_time` — Availability end

### PTSession

Stores personal training appointments.

Attributes:
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

### Personal Training Scheduling

- Book a personal training session.
- Reschedule an existing session.
- Cancel a scheduled session.
- Prevent overlapping active sessions for the same trainer or member.
- Reject bookings outside the trainer's available hours.

### Trainer Schedule

- Retrieve scheduled personal training sessions.
- Display appointments chronologically.
- Represent both PT sessions and group classes using a shared schedule-entry structure.

Group-class database retrieval requires integration with the administrative module.

### Assigned-Member Lookup

- Retrieve members assigned to a trainer through scheduled PT sessions.
- Search assigned members by first name, last name, or full name.
- Perform case-insensitive searches.
- Treat SQL wildcard characters as literal search characters.
- Restrict results to members assigned to the selected trainer.

Health metrics and fitness-goal retrieval require integration with the member module.

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

## 6. Implementation Structure

- `app/models/trainer.py` — SQLAlchemy ORM models.
- `app/trainers/trainer_service.py` — Scheduling and member-lookup business logic.
- `app/trainers/trainer_cli.py` — Trainer command-line interface.
- `app/trainers/schedule.py` — Unified schedule representation.
- `tests/test_trainers.py` — Database and service tests.
- `tests/test_trainer_cli.py` — CLI tests.
- `tests/test_trainer_schedule.py` — Schedule representation tests.

## 7. Testing

The trainer module currently has 54 passing automated tests:

- 36 database and service tests.
- 14 command-line interface tests.
- 4 schedule representation tests.

The tests cover valid operations, invalid inputs, overlapping appointments, cancellation, rescheduling, name searching, and schedule display.

Code quality is checked using Ruff.

## 8. Remaining Integration Work

The following tasks require coordination with the other project members:

1. Integrate member health metrics and current fitness goals into assigned-member lookup.
2. Retrieve group fitness classes and include them in trainer schedules.
3. Implement room assignment and room-conflict validation for personal training sessions.
4. Register all shared ORM models and verify database initialization.
5. Connect the trainer menu to the application's main entry point.
6. Run complete integration tests and demonstrate the combined application.

## 9. Current Status

The independent trainer-management functionality is implemented and passes its automated tests.

Cross-module features remain pending until the shared Member, FitnessGoal, HealthMetric, FitnessClass, and Room models are available.