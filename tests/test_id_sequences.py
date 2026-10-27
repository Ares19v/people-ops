"""Generated ids must continue after rows that already exist (they used to restart at 1 on every restart)."""
import sqlite3

import pytest

from app.core import id_generator
from app.core.config import settings
from app.core.id_generator import generate_entity_id


@pytest.fixture
def fresh_sequences(monkeypatch, tmp_path):
    db_file = tmp_path / "ids.db"
    connection = sqlite3.connect(db_file)
    connection.execute("create table leave_applications (id text primary key)")
    connection.execute("create table timesheet_entries (id text primary key)")
    connection.executemany("insert into leave_applications values (?)",
                           [("leave_zed.user_1",), ("leave_zed.user_7",), ("leave_other.person_9",), ("leave_zed.user_note",)])
    connection.execute("insert into timesheet_entries values ('ts_zed.user_3')")
    connection.commit()
    connection.close()
    monkeypatch.setattr(settings, "SYNC_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setattr(id_generator, "_sync_engine", None)
    monkeypatch.setattr(id_generator, "_seeded", set())
    monkeypatch.setattr(id_generator, "_counters", {})


def test_new_ids_continue_after_the_highest_stored_index(fresh_sequences):
    assert generate_entity_id("leave", "zed.user@intelera.com") == "leave_zed.user_8"
    assert generate_entity_id("leave", "zed.user@intelera.com") == "leave_zed.user_9"
    assert generate_entity_id("leave", "other.person@intelera.com") == "leave_other.person_10"
    assert generate_entity_id("timesheet", "zed.user@intelera.com") == "ts_zed.user_4"


def test_buckets_without_rows_or_tables_start_at_one(fresh_sequences):
    assert generate_entity_id("leave", "nobody.here@intelera.com") == "leave_nobody.here_1"
    assert generate_entity_id("session", "zed.user@intelera.com") == "sess_zed.user_1"  # chat_sessions table is absent


def test_seeded_employee_no_longer_collides_with_the_demo_data():
    """The demo data contains leave_aarav.sharma_1/_2; the first new application used to be leave_aarav.sharma_1."""
    import re
    from data import seed_data

    source = open(seed_data.__file__, encoding="utf-8").read()
    assert 'id="leave_aarav.sharma_1"' in source and re.search(r'id="ts_aarav.sharma_2"', source)


# ── The two data-writing tools the ADK comparison exposed ─────────────────────

async def test_apply_leave_tool_reports_success_for_a_saved_application():
    """It used to commit the row and then fail building its reply (`application.days`), so the agent told the
    employee the request had failed (and retried) although the leave was already submitted."""
    from app.tools.leave.apply_leave import apply_leave

    result = await apply_leave(user_id="EMP-004", leave_type="CL", start_date="2031-03-03", end_date="2031-03-04",
                               reason="regression test")
    assert "error" not in result, result
    assert result["days"] == 2.0 and result["status"] == "SUBMITTED" and result["leave_type"] == "CL"
    # ids continue after the demo data's leave_aarav.sharma_1/_2 instead of colliding with them
    assert result["application_id"].startswith("leave_aarav.sharma_")
    assert int(result["application_id"].rsplit("_", 1)[1]) >= 3


async def test_log_work_hours_tool_does_not_collide_with_existing_entries():
    from app.tools.timesheet.log_work_hours import log_work_hours

    result = await log_work_hours(user_id="EMP-004", project_name="PROJ-BNK-01", task_name="regression test",
                                  hours=1.0, entry_date="2031-03-03", is_billable=True)
    assert "error" not in result, result
