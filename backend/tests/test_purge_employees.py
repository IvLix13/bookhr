from datetime import date

from app.extensions import db
from app.models import (
    EmployeeGradeHistory,
    Employment,
    GradeCatalog,
    ImportJob,
    ImportStatus,
    ImportType,
    Person,
    Role,
    RoleName,
    User,
)
from app.services.employees import create_person_with_employment
from app.services.purge_employees import purge_all_employees


def test_purge_all_employees_keeps_grade_catalog(app, seed_company):
    with app.app_context():
        admin_role = Role(name=RoleName.ADMIN.value)
        db.session.add(admin_role)
        db.session.flush()
        user = User(username="purger", full_name="Purger", role_id=admin_role.id)
        user.set_password("secret123")
        db.session.add(user)

        kept_grade = GradeCatalog(name="Сохраняемый", rank=99, min_years=1, is_active=True)
        assigned_grade = GradeCatalog(name="Назначенный", rank=1, min_years=1, is_active=True)
        db.session.add_all([kept_grade, assigned_grade])
        db.session.flush()

        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Удаляемый Сотрудник",
            hire_date=date(2020, 1, 1),
            title="Инженер",
            position_grade_id=assigned_grade.id,
            education_status="yes",
        )
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=assigned_grade.id,
                assigned_date=date(2024, 1, 1),
            )
        )

        job = ImportJob(
            company_id=seed_company.id,
            filename="employees.xlsx",
            import_type=ImportType.EMPLOYEES.value,
            status=ImportStatus.UPLOADED.value,
            uploaded_by_id=user.id,
        )
        db.session.add(job)
        db.session.commit()

        grade_count = GradeCatalog.query.count()
        result = purge_all_employees()

        assert result.employments_deleted == 1
        assert result.persons_deleted == 1
        assert result.import_jobs_deleted == 1
        assert result.grade_catalog_before == grade_count
        assert result.grade_catalog_after == grade_count
        assert Employment.query.count() == 0
        assert Person.query.count() == 0
        assert ImportJob.query.filter_by(import_type=ImportType.EMPLOYEES.value).count() == 0
        assert GradeCatalog.query.filter_by(name="Сохраняемый").count() == 1
        assert GradeCatalog.query.filter_by(name="Назначенный").count() == 1
