from datetime import date
import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.extensions import db
from app.models import AuditLog, Company, Employment, Person, PersonNameHistory, GradeCatalog, EmployeeGradeHistory
from app.models.onboarding import OnboardingCell, OnboardingColumn, OnboardingPlan
from app.services.purge_employees import purge_all_employees


def employee(company_id, name="Иванов Иван"):
    person = Person()
    db.session.add(person)
    db.session.flush()
    db.session.add(PersonNameHistory(person_id=person.id, full_name=name, valid_from=date(2020, 1, 1)))
    row = Employment(person_id=person.id, company_id=company_id, hire_date=date(2020, 1, 1))
    db.session.add(row)
    db.session.commit()
    return row.id


def data(response, status=200):
    assert response.status_code == status, response.get_json()
    return response.get_json()["data"]


def setup_plan(client, company_id, kind="stage"):
    with client.application.app_context():
        employment_id = employee(company_id)
    plan = data(client.post("/api/onboarding/plans", json={"employment_id": employment_id}), 201)
    column = data(client.post("/api/onboarding/columns", json={"title": "NDA", "field_type": kind}), 201)
    return plan, column


def patch_cell(client, plan, column, **payload):
    return client.patch(f'/api/onboarding/plans/{plan["id"]}/cells/{column["id"]}',
                        json={"version": 0, "column_version": column["version"], **payload})


def test_stage_lifecycle_and_audit(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    cell = data(patch_cell(hr_client, plan, column, planned_date="2026-10-01"))
    done = data(patch_cell(hr_client, plan, column, version=cell["version"], is_completed=True, completed_date="2026-09-19"))
    assert done["planned_date"] == "2026-10-01"
    assert done["is_completed"] is True
    undone = data(patch_cell(hr_client, plan, column, version=done["version"], is_completed=False))
    assert undone["completed_date"] is None
    assert undone["planned_date"] == "2026-10-01"
    result = data(hr_client.get("/api/onboarding/plans"))
    assert result["items"][0]["cells"][str(column["id"])] == undone
    assert data(hr_client.get(f'/api/onboarding/plans/{plan["id"]}'))["full_name"] == "Иванов Иван"
    with hr_client.application.app_context():
        logs = AuditLog.query.filter_by(entity_type="onboarding_cell").all()
        assert len(logs) == 3
        assert logs[-1].old_value["completed_date"] == "2026-09-19"
        assert logs[-1].user_id is not None


def test_completion_without_plan_and_date_edit(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    cell = data(patch_cell(hr_client, plan, column, is_completed=True, completed_date="2026-09-19"))
    assert cell["planned_date"] is None
    changed = data(patch_cell(hr_client, plan, column, version=cell["version"], completed_date="2026-09-18"))
    assert changed["completed_date"] == "2026-09-18"


@pytest.mark.parametrize("payload", [
    {"is_completed": True}, {"planned_date": "bad"}, {"completed_date": "2026-02-30"},
    {"text_value": "wrong type"}, {"is_completed": "false"}, {"unknown": "x"},
])
def test_invalid_cells(hr_client, seed_company, payload):
    plan, column = setup_plan(hr_client, seed_company.id)
    assert patch_cell(hr_client, plan, column, **payload).status_code == 400
    with hr_client.application.app_context():
        assert OnboardingCell.query.count() == 0


@pytest.mark.parametrize("kind,values", [("text", {"text_value": "IT"}), ("date", {"date_value": "2026-09-19"})])
def test_types_and_clear(hr_client, seed_company, kind, values):
    plan, column = setup_plan(hr_client, seed_company.id, kind)
    cell = data(patch_cell(hr_client, plan, column, **values))
    key = next(iter(values))
    assert cell[key] == values[key]
    cleared = data(patch_cell(hr_client, plan, column, version=cell["version"], **{key: None}))
    assert cleared[key] is None


def test_stale_cell_and_column(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    data(patch_cell(hr_client, plan, column, planned_date="2026-10-01"))
    assert patch_cell(hr_client, plan, column, planned_date="2026-10-02").status_code == 409
    updated = data(hr_client.patch(f'/api/onboarding/columns/{column["id"]}', json={"version": column["version"], "title": "New"}))
    assert updated["version"] > column["version"]
    assert hr_client.patch(f'/api/onboarding/columns/{column["id"]}', json={"version": column["version"], "title": "Lost"}).status_code == 409
    assert patch_cell(hr_client, plan, column, version=1, planned_date="2026-10-03").status_code == 409


def test_archive_restore_rename_reorder_and_type_guard(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    cell = data(patch_cell(hr_client, plan, column, planned_date="2026-10-01"))
    url = f'/api/onboarding/columns/{column["id"]}'
    assert hr_client.patch(url, json={"version": 1, "field_type": "text"}).status_code == 400
    archived = data(hr_client.patch(url, json={"version": 1, "is_archived": True}))
    assert patch_cell(hr_client, plan, archived, version=cell["version"], planned_date="2026-10-02").status_code == 409
    assert hr_client.patch(url, json={"version": archived["version"], "field_type": "text"}).status_code == 400
    restored = data(hr_client.patch(url, json={"version": archived["version"], "is_archived": False, "title": "Agreement"}))
    second = data(hr_client.post("/api/onboarding/columns", json={"title": "Отдел", "field_type": "text"}), 201)
    order = [{"id": c["id"], "version": c["version"]} for c in [second, restored]]
    data(hr_client.patch("/api/onboarding/columns/order", json={"columns": order}))
    assert [c["id"] for c in data(hr_client.get("/api/onboarding/columns"))] == [second["id"], restored["id"]]
    cells = data(hr_client.get("/api/onboarding/plans"))["items"][0]["cells"]
    assert cells[str(column["id"])]["planned_date"] == "2026-10-01"
    assert str(second["id"]) not in cells
    assert hr_client.patch("/api/onboarding/columns/order", json={"columns": order}).status_code == 409
    assert hr_client.patch("/api/onboarding/columns/order", json={"columns": []}).status_code == 409


def test_empty_type_change_and_protected_fields(admin_client, seed_company):
    plan, column = setup_plan(admin_client, seed_company.id, "text")
    data(patch_cell(admin_client, plan, column, text_value=""))
    data(admin_client.patch(f'/api/onboarding/columns/{column["id"]}', json={"version": 1, "field_type": "date"}))
    assert admin_client.patch(f'/api/onboarding/plans/{plan["id"]}', json={"full_name": "hack"}).status_code == 405
    assert admin_client.post("/api/onboarding/columns", json={"title": " ", "field_type": "text"}).status_code == 400
    assert admin_client.post("/api/onboarding/columns", json={"title": "x", "field_type": "sql"}).status_code == 400


def test_tenant_isolation(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    with hr_client.application.app_context():
        company = Company(name="Other")
        db.session.add(company)
        db.session.commit()
        other_employee = employee(company.id)
        other_column = OnboardingColumn(company_id=company.id, title="Secret", field_type="text", sort_order=0)
        other_plan = OnboardingPlan(employment_id=other_employee)
        db.session.add_all([other_column, other_plan])
        db.session.commit()
        cid, pid = other_column.id, other_plan.id
    assert len(data(hr_client.get("/api/onboarding/columns"))) == 1
    assert data(hr_client.get("/api/onboarding/plans"))["total"] == 1
    assert hr_client.post("/api/onboarding/plans", json={"employment_id": other_employee}).status_code == 404
    assert hr_client.get(f"/api/onboarding/plans/{pid}").status_code == 404
    assert hr_client.patch(f"/api/onboarding/columns/{cid}", json={"version": 1, "title": "hack"}).status_code == 404
    assert patch_cell(hr_client, plan, {"id": cid, "version": 1}, text_value="hack").status_code == 404
    assert patch_cell(hr_client, {"id": pid}, column, planned_date=None).status_code == 404


def test_viewer_and_anonymous_permissions(viewer_client):
    assert viewer_client.get("/api/onboarding/plans").status_code == 200
    assert viewer_client.get("/api/onboarding/columns").status_code == 200
    for method, path in [("post", "plans"), ("post", "columns"), ("patch", "columns/1"), ("patch", "columns/order"), ("patch", "plans/1/cells/1")]:
        assert getattr(viewer_client, method)(f"/api/onboarding/{path}", json={}).status_code == 403


def test_anonymous_cannot_read(client):
    assert client.get("/api/onboarding/plans").status_code == 401
    assert client.get("/api/onboarding/columns").status_code == 401


def test_duplicate_dismissal_deletion_and_rehire(hr_client, seed_company):
    plan, _ = setup_plan(hr_client, seed_company.id)
    assert hr_client.post("/api/onboarding/plans", json={"employment_id": plan["employment_id"]}).status_code == 409
    assert hr_client.delete(f'/api/employees/{plan["employment_id"]}').status_code == 400
    with hr_client.application.app_context():
        with pytest.raises(ValueError):
            purge_all_employees()
        employment = db.session.get(Employment, plan["employment_id"])
        employment.status = "dismissed"
        again = Employment(person_id=employment.person_id, company_id=seed_company.id, hire_date=date(2026, 9, 19))
        db.session.add(again)
        db.session.commit()
        new_id = again.id
    data(hr_client.post("/api/onboarding/plans", json={"employment_id": new_id}), 201)
    listed = data(hr_client.get("/api/onboarding/plans"))
    assert listed["total"] == 2
    assert listed["items"][0]["employment_status"] == "dismissed"


def test_current_name_grade_search_pagination(hr_client, seed_company):
    plan, _ = setup_plan(hr_client, seed_company.id)
    with hr_client.application.app_context():
        employment = db.session.get(Employment, plan["employment_id"])
        employment.person.name_history[0].full_name = "Петров"
        grade = GradeCatalog(name="Junior", rank=1, min_years=1)
        db.session.add(grade)
        db.session.flush()
        db.session.add(EmployeeGradeHistory(employment_id=employment.id, grade_id=grade.id, assigned_date=date(2026, 1, 1)))
        db.session.commit()
    rows = data(hr_client.get("/api/onboarding/plans?q=Петров&per_page=1"))
    assert rows["items"][0]["grade"] == "Junior"
    assert rows["items"][0]["full_name"] == "Петров"
    assert data(hr_client.get("/api/onboarding/plans?q=Несуществующий"))["total"] == 0
    assert data(hr_client.get("/api/onboarding/plans?page=2&per_page=1"))["items"] == []


def test_migration_preserves_existing_data():
    migration = importlib.import_module("migrations.versions.0016_onboarding")
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE companies (id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql("CREATE TABLE employments (id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql("INSERT INTO companies VALUES (1)")
        conn.exec_driver_sql("INSERT INTO employments VALUES (1)")
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM onboarding_columns").scalar() == 6
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM onboarding_plans").scalar() == 0
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM employments").scalar() == 1
            migration.downgrade()
            migration.upgrade()
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM onboarding_columns").scalar() == 6


def test_list_queries_do_not_grow_per_row_or_cell(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    data(patch_cell(hr_client, plan, column, planned_date="2026-10-01"))
    with hr_client.application.app_context():
        engine = db.engine
        def count_queries():
            statements = []
            def record(conn, cursor, statement, parameters, context, executemany):
                if statement.lstrip().upper().startswith("SELECT"):
                    statements.append(statement)
            db.session.expire_all()
            sa.event.listen(engine, "before_cursor_execute", record)
            try:
                data(hr_client.get("/api/onboarding/plans"))
            finally:
                sa.event.remove(engine, "before_cursor_execute", record)
            return len(statements)
        before = count_queries()
        for i in range(12):
            eid = employee(seed_company.id, f"Сотрудник {i}")
            db.session.add(OnboardingPlan(employment_id=eid))
        db.session.commit()
        after = count_queries()
        assert after == before


def test_csrf_required_for_new_routes(hr_client):
    app = hr_client.application
    app.config["TESTING"] = False
    try:
        response = hr_client.post("/api/onboarding/columns", json={"title": "Отдел", "field_type": "text"})
        assert response.status_code == 403
        token = data(hr_client.get("/api/csrf"))["csrf_token"]
        data(hr_client.post("/api/onboarding/columns", headers={"X-CSRF-Token": token},
                            json={"title": "Отдел", "field_type": "text"}), 201)
    finally:
        app.config["TESTING"] = True
