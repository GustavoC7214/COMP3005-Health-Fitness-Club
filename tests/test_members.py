"""Member 1 operations, real PostgreSQL integrity, and dashboard edge cases."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.member_setup import install_member_view, seed_member_demo
from app.members.member_queries import DashboardIntegrations, dashboard_view
from app.members.member_service import (
    DuplicateEmailError,
    GoalNotFoundError,
    MemberNotFoundError,
    create_fitness_goal,
    get_fitness_goals,
    get_health_history,
    get_member,
    get_member_dashboard,
    record_health_metric,
    register_member,
    update_fitness_goal,
    update_profile,
)
from app.models.member import FitnessGoal, HealthMetric, Member
from app.utils.validators import ValidationError


def register(session, email="benson@example.com"):
    return register_member(
        session,
        first_name="Benson",
        last_name="Li",
        email=email,
        date_of_birth="2000-06-01",
        gender="Prefer not to say",
        phone="613-555-0101",
    )


def test_registration_persists_in_new_session(m1_session, m1_engine):
    member = register(m1_session, " Benson@Example.COM ")
    m1_session.commit()
    with Session(m1_engine) as other:
        saved = get_member(other, member.member_id)
        assert saved.email == "benson@example.com"
        assert saved.first_name == "Benson"
        assert saved.phone == "613-555-0101"


def test_duplicate_registration_uses_db_constraint(m1_session):
    register(m1_session)
    m1_session.commit()
    with pytest.raises(DuplicateEmailError):
        register(m1_session, "BENSON@example.com")
    m1_session.rollback()
    assert m1_session.scalar(select(func.count()).select_from(Member)) == 1
    register(m1_session, "another@example.com")  # session works after rollback


@pytest.mark.parametrize(
    "changes",
    [
        {"first_name": " "},
        {"last_name": None},
        {"email": "bad"},
        {"email": "a@b.com extra"},
        {"date_of_birth": "bad"},
        {"date_of_birth": "2999-01-01"},
        {"first_name": "x" * 101},
        {"phone": "x" * 31},
        {"gender": 42},
    ],
)
def test_invalid_registration(m1_session, changes):
    values = {
        "first_name": "Benson",
        "last_name": "Li",
        "email": "b@example.com",
        "date_of_birth": "2000-01-01",
    }
    values.update(changes)
    with pytest.raises(ValidationError):
        register_member(m1_session, **values)
    assert m1_session.scalar(select(func.count()).select_from(Member)) == 0


def test_profile_updates_persist_and_clear_optional_fields(m1_session, m1_engine):
    member = register(m1_session)
    update_profile(
        m1_session,
        member.member_id,
        first_name="New",
        email=" NEW@example.com ",
        phone="",
    )
    m1_session.commit()
    with Session(m1_engine) as other:
        saved = get_member(other, member.member_id)
        assert (saved.first_name, saved.email, saved.phone) == (
            "New",
            "new@example.com",
            None,
        )


def test_profile_duplicate_email_rolls_back(m1_session):
    a = register(m1_session)
    b = register(m1_session, "other@example.com")
    m1_session.commit()
    with pytest.raises(DuplicateEmailError):
        update_profile(m1_session, b.member_id, email=a.email)
    m1_session.rollback()
    assert get_member(m1_session, b.member_id).email == "other@example.com"


def test_invalid_profile_does_not_partially_mutate(m1_session):
    member = register(m1_session)
    with pytest.raises(ValidationError):
        update_profile(
            m1_session, member.member_id, first_name="Changed", email="invalid"
        )
    assert member.first_name == "Benson"
    with pytest.raises(ValidationError):
        update_profile(m1_session, member.member_id, unsupported_field=2)


def test_empty_profile_update_rejected(m1_session):
    member = register(m1_session)
    with pytest.raises(ValidationError):
        update_profile(m1_session, member.member_id)


@pytest.mark.parametrize(
    "operation",
    [
        lambda s: update_profile(s, 999, first_name="New"),
        lambda s: create_fitness_goal(s, 999, target_weight_kg=70),
        lambda s: record_health_metric(s, 999, weight_kg=70),
        lambda s: get_health_history(s, 999),
        lambda s: get_member_dashboard(s, 999),
    ],
)
def test_nonexistent_member(m1_session, operation):
    with pytest.raises(MemberNotFoundError):
        operation(m1_session)


def test_goals_create_update_and_persist(m1_session, m1_engine):
    member = register(m1_session)
    record_health_metric(m1_session, member.member_id, weight_kg=80)
    goal = create_fitness_goal(m1_session, member.member_id, target_weight_kg=75)
    assert goal.baseline_weight_kg == Decimal(80)
    update_fitness_goal(
        m1_session,
        member.member_id,
        goal.goal_id,
        target_weight_kg=74,
        status="completed",
    )
    m1_session.commit()
    with Session(m1_engine) as other:
        saved = get_fitness_goals(other, member.member_id)[0]
        assert saved.target_weight_kg == Decimal(74)
        assert saved.baseline_weight_kg == Decimal(80)
        assert saved.status == "completed"


def test_goal_ownership_and_invalid_updates(m1_session):
    member = register(m1_session)
    other = register(m1_session, "other@example.com")
    goal = create_fitness_goal(m1_session, member.member_id, target_weight_kg=70)
    with pytest.raises(GoalNotFoundError):
        update_fitness_goal(
            m1_session, other.member_id, goal.goal_id, status="completed"
        )
    for changes in (
        {"target_weight_kg": -5},
        {"status": "bad"},
        {"target_date": "1900-01-01"},
        {},
    ):
        with pytest.raises(ValidationError):
            update_fitness_goal(m1_session, member.member_id, goal.goal_id, **changes)
    with pytest.raises(GoalNotFoundError):
        update_fitness_goal(m1_session, member.member_id, 9999, status="completed")


def test_history_preserves_old_rows_and_orders_by_timestamp(m1_session, m1_engine):
    member = register(m1_session)
    older = datetime.now(UTC) - timedelta(days=2)
    first = record_health_metric(
        m1_session,
        member.member_id,
        weight_kg=80,
        height_cm=175,
        heart_rate_bpm=72,
        recorded_at=older,
    )
    first_id = first.metric_id
    second = record_health_metric(
        m1_session,
        member.member_id,
        weight_kg=78,
        recorded_at=older + timedelta(days=1),
    )
    # Insert an even older observation last: insertion order must not define latest.
    record_health_metric(
        m1_session,
        member.member_id,
        weight_kg=82,
        recorded_at=older - timedelta(days=1),
    )
    m1_session.commit()
    with Session(m1_engine) as other:
        history = get_health_history(other, member.member_id)
        assert len(history) == 3
        assert history[0].metric_id == second.metric_id
        old = other.get(HealthMetric, first_id)
        assert (old.weight_kg, old.height_cm, old.heart_rate_bpm, old.recorded_at) == (
            Decimal(80),
            Decimal(175),
            72,
            older,
        )
        assert (
            get_member_dashboard(other, member.member_id).latest_metric.metric_id
            == second.metric_id
        )


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"weight_kg": 0},
        {"weight_kg": -1},
        {"weight_kg": "NaN"},
        {"weight_kg": "Infinity"},
        {"weight_kg": True},
        {"weight_kg": "75.123"},
        {"height_cm": 301},
        {"heart_rate_bpm": 301},
        {"heart_rate_bpm": "70.5"},
        {"weight_kg": 70, "recorded_at": "2020-01-01T12:00:00"},
        {"weight_kg": 70, "recorded_at": "2999-01-01T12:00:00+00:00"},
    ],
)
def test_invalid_health_metrics(m1_session, values):
    member = register(m1_session)
    with pytest.raises(ValidationError):
        record_health_metric(m1_session, member.member_id, **values)
    assert get_health_history(m1_session, member.member_id) == []


def test_empty_dashboard_and_history(m1_session):
    member = register(m1_session)
    dashboard = get_member_dashboard(m1_session, member.member_id)
    assert dashboard.latest_metric is None
    assert dashboard.goals == []
    assert dashboard.past_class_count == 0  # real count of an empty attendance table
    assert dashboard.upcoming_sessions is None
    assert get_health_history(m1_session, member.member_id) == []
    assert len(dashboard.integration_notes) == 1  # only PT remains external


def test_dashboard_progress_and_partial_latest_record(m1_session):
    member = register(m1_session)
    record_health_metric(m1_session, member.member_id, weight_kg=80)
    goal = create_fitness_goal(m1_session, member.member_id, target_weight_kg=75)
    record_health_metric(m1_session, member.member_id, weight_kg=78)
    partial = record_health_metric(m1_session, member.member_id, heart_rate_bpm=65)
    dashboard = get_member_dashboard(m1_session, member.member_id)
    assert dashboard.latest_metric.metric_id == partial.metric_id
    assert dashboard.latest_metric.weight_kg is None
    assert dashboard.goals[0].current_weight_kg == Decimal(78)
    assert dashboard.goals[0].progress_percent == Decimal("40.00")
    update_fitness_goal(m1_session, member.member_id, goal.goal_id, status="completed")
    assert get_member_dashboard(m1_session, member.member_id).goals == []


@pytest.mark.parametrize(
    "baseline,target,current,expected",
    [(60, 70, 65, 50), (80, 75, 73, 100), (80, 75, 82, 0), (80, 80, 80, 100)],
)
def test_progress_gain_loss_and_bounds(m1_session, baseline, target, current, expected):
    member = register(m1_session)
    record_health_metric(m1_session, member.member_id, weight_kg=baseline)
    create_fitness_goal(m1_session, member.member_id, target_weight_kg=target)
    record_health_metric(m1_session, member.member_id, weight_kg=current)
    assert (
        get_member_dashboard(m1_session, member.member_id).goals[0].progress_percent
        == expected
    )


def test_goal_without_baseline_is_explicitly_unavailable(m1_session):
    member = register(m1_session)
    create_fitness_goal(m1_session, member.member_id, target_weight_kg=75)
    record_health_metric(m1_session, member.member_id, weight_kg=78)
    assert (
        get_member_dashboard(m1_session, member.member_id).goals[0].progress_percent
        is None
    )


def test_view_tie_breaking_and_member_isolation(m1_session):
    a = register(m1_session)
    b = register(m1_session, "other@example.com")
    at = datetime.now(UTC) - timedelta(days=1)
    record_health_metric(m1_session, a.member_id, weight_kg=80, recorded_at=at)
    last = record_health_metric(m1_session, a.member_id, weight_kg=79, recorded_at=at)
    record_health_metric(m1_session, b.member_id, weight_kg=55)
    assert (
        get_member_dashboard(m1_session, a.member_id).latest_metric.metric_id
        == last.metric_id
    )
    summary = (
        m1_session.execute(
            select(dashboard_view).where(dashboard_view.c.member_id == a.member_id)
        )
        .mappings()
        .one()
    )
    assert summary["latest_weight_kg"] == Decimal(79)
    assert summary["active_goal_count"] == 0


def test_attendance_callback_executes_query_with_selected_member(m1_session):
    # Query transport only; this does not claim real attendance integration.
    member = register(m1_session)

    def db_reader(session, member_id, as_of):
        assert session is m1_session
        assert as_of.tzinfo is not None
        return session.scalar(
            select(func.count())
            .select_from(Member)
            .where(Member.member_id == member_id)
        )

    result = get_member_dashboard(
        m1_session,
        member.member_id,
        integrations=DashboardIntegrations(past_class_count=db_reader),
    )
    assert result.past_class_count == 1
    assert not any("Class attendance" in note for note in result.integration_notes)


@pytest.mark.parametrize("bad", [None, -1, True, "3"])
def test_invalid_attendance_adapter_response(m1_session, bad):
    member = register(m1_session)
    with pytest.raises(ValueError):
        get_member_dashboard(
            m1_session,
            member.member_id,
            integrations=DashboardIntegrations(past_class_count=lambda *args: bad),
        )


@pytest.mark.parametrize(
    "entity,values",
    [
        (
            Member,
            {
                "first_name": "B",
                "last_name": "L",
                "email": "UPPER@example.com",
                "date_of_birth": "2000-01-01",
            },
        ),
        (
            Member,
            {
                "first_name": "",
                "last_name": "L",
                "email": "b@example.com",
                "date_of_birth": "2000-01-01",
            },
        ),
        (
            Member,
            {
                "first_name": "B",
                "last_name": "L",
                "email": "b@example.com",
                "date_of_birth": "2999-01-01",
            },
        ),
        (HealthMetric, {"member_id": 1, "weight_kg": -1}),
        (HealthMetric, {"member_id": 1}),
        (FitnessGoal, {"member_id": 1, "target_weight_kg": 0}),
        (FitnessGoal, {"member_id": 1, "target_weight_kg": 75, "status": "invalid"}),
    ],
)
def test_database_checks_reject_bypassed_service(m1_session, entity, values):
    member = register(m1_session)
    m1_session.commit()
    if "member_id" in values:
        values = {**values, "member_id": member.member_id}
    m1_session.add(entity(**values))
    with pytest.raises(IntegrityError):
        m1_session.flush()
    m1_session.rollback()


def test_database_foreign_key_rejects_orphans(m1_session):
    m1_session.add(HealthMetric(member_id=9999, weight_kg=70))
    with pytest.raises(IntegrityError):
        m1_session.flush()


def test_view_install_is_repeatable_and_demo_is_opt_in(m1_engine):
    install_member_view(m1_engine)
    with Session(m1_engine) as session:
        member_id = seed_member_demo(session)
        assert seed_member_demo(session) == member_id
        session.commit()
    with Session(m1_engine) as session:
        result = get_member_dashboard(session, member_id)
        assert result.goals[0].progress_percent == Decimal(40)
        assert len(get_health_history(session, member_id)) == 2


def test_read_view_does_not_create_physical_dashboard_table(m1_session):
    kind = m1_session.scalar(
        text("SELECT relkind FROM pg_class WHERE oid = 'member_dashboard'::regclass")
    )
    assert kind == "v"
