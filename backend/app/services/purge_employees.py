"""Hard-delete all employee data while keeping the grade catalog."""

from __future__ import annotations

from dataclasses import dataclass

from app.extensions import db
from app.models import (
    Employment,
    GradeCatalog,
    ImportJob,
    ImportRow,
    ImportType,
    Person,
)
from app.services.employees import delete_employment


@dataclass(frozen=True)
class PurgeEmployeesResult:
    employments_deleted: int
    persons_deleted: int
    import_jobs_deleted: int
    grade_catalog_before: int
    grade_catalog_after: int


def purge_all_employees() -> PurgeEmployeesResult:
    """Remove every employee/person and related records. Grade catalog is preserved."""
    grade_catalog_before = GradeCatalog.query.count()
    persons_before = Person.query.count()

    employment_ids = [
        employment_id
        for (employment_id,) in db.session.query(Employment.id).order_by(Employment.id.asc())
    ]
    for employment_id in employment_ids:
        employment = db.session.get(Employment, employment_id)
        if employment is not None:
            delete_employment(employment)

    import_job_ids = [
        job_id
        for (job_id,) in db.session.query(ImportJob.id).filter(
            ImportJob.import_type.in_(
                (ImportType.EMPLOYEES.value, ImportType.REWARDS.value),
            ),
        )
    ]
    if import_job_ids:
        ImportRow.query.filter(ImportRow.import_job_id.in_(import_job_ids)).delete(
            synchronize_session=False,
        )
        ImportJob.query.filter(ImportJob.id.in_(import_job_ids)).delete(
            synchronize_session=False,
        )

    db.session.commit()

    grade_catalog_after = GradeCatalog.query.count()
    if grade_catalog_after != grade_catalog_before:
        raise RuntimeError(
            "Grade catalog row count changed during purge: "
            f"{grade_catalog_before} -> {grade_catalog_after}",
        )

    persons_after = Person.query.count()
    if persons_after != 0:
        raise RuntimeError(f"Expected 0 persons after purge, found {persons_after}")

    if Employment.query.count() != 0:
        raise RuntimeError("Expected 0 employments after purge")

    return PurgeEmployeesResult(
        employments_deleted=len(employment_ids),
        persons_deleted=persons_before,
        import_jobs_deleted=len(import_job_ids),
        grade_catalog_before=grade_catalog_before,
        grade_catalog_after=grade_catalog_after,
    )
