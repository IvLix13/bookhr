"""Import API."""

from __future__ import annotations

import uuid
from pathlib import Path

from flask import current_app, request, send_file
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.api.helpers import api_response, get_json, require_roles
from app.api.serializers import import_job_to_dict
from app.extensions import db
from app.models import ImportJob, ImportStatus, ImportType, RoleName
from app.services.import_excel import confirm_import, dry_run_import, export_template, parse_workbook
from app.services.import_rewards import (
    confirm_rewards_import,
    dry_run_rewards_import,
    export_rewards_template,
    parse_rewards_workbook,
)


def _resolve_import_type(raw: str | None) -> ImportType | None:
    if raw is None or raw == "":
        return ImportType.EMPLOYEES
    try:
        return ImportType(str(raw).strip().lower())
    except ValueError:
        return None


def register_routes(bp):
    @bp.post("/import/upload")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def upload_import():
        if "file" not in request.files:
            return api_response(message="File required", status=400)

        file = request.files["file"]
        if not file.filename or not file.filename.lower().endswith(".xlsx"):
            return api_response(message="Only .xlsx files allowed", status=400)

        import_type = _resolve_import_type(
            request.form.get("import_type") or request.args.get("import_type")
        )
        if import_type is None:
            return api_response(message="Invalid import type", status=400)

        company_id = request.form.get("company_id", 1, type=int)
        upload_dir = Path(current_app.config["UPLOAD_DIR"])
        upload_dir.mkdir(parents=True, exist_ok=True)

        filename = secure_filename(file.filename)
        stored_name = f"{uuid.uuid4()}_{filename}"
        path = upload_dir / stored_name
        file.save(path)

        job = ImportJob(
            company_id=company_id,
            filename=filename,
            import_type=import_type.value,
            uploaded_by_id=current_user.id,
        )
        db.session.add(job)
        db.session.flush()

        if import_type == ImportType.REWARDS:
            rows = parse_rewards_workbook(path)
            dry_run_rewards_import(job, rows)
        else:
            rows = parse_workbook(path)
            dry_run_import(job, rows)
        db.session.commit()
        return api_response(import_job_to_dict(job), status=201)

    @bp.post("/import/<int:job_id>/confirm")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def confirm(job_id: int):
        job = db.session.get(ImportJob, job_id)
        if not job:
            return api_response(message="Not found", status=404)
        if job.status != ImportStatus.VALIDATED.value:
            return api_response(message="Import not validated", status=400)

        payload = get_json()
        row_actions = {int(k): v for k, v in payload.get("row_actions", {}).items()}
        try:
            if job.import_type == ImportType.REWARDS.value:
                confirm_rewards_import(job, row_actions)
            else:
                confirm_import(job, row_actions)
        except Exception:  # noqa: BLE001 — job is marked FAILED inside confirm_*
            current_app.logger.exception("Import confirm failed for job %s", job_id)
            return api_response(
                import_job_to_dict(job),
                message="Import failed",
                status=500,
            )
        return api_response(import_job_to_dict(job))

    @bp.get("/import/<int:job_id>")
    @login_required
    def get_job(job_id: int):
        job = db.session.get(ImportJob, job_id)
        if not job:
            return api_response(message="Not found", status=404)
        return api_response(import_job_to_dict(job))

    @bp.get("/import/template")
    @login_required
    def download_template():
        import_type = _resolve_import_type(request.args.get("import_type"))
        if import_type is None:
            return api_response(message="Invalid import type", status=400)

        company_id = request.args.get("company_id", 1, type=int)
        upload_dir = Path(current_app.config["UPLOAD_DIR"])
        upload_dir.mkdir(parents=True, exist_ok=True)

        if import_type == ImportType.REWARDS:
            path = upload_dir / f"rewards_template_{company_id}.xlsx"
            export_rewards_template(company_id, path)
            download_name = "rewards_template.xlsx"
        else:
            path = upload_dir / f"template_{company_id}.xlsx"
            export_template(company_id, path)
            download_name = "employees_template.xlsx"

        return send_file(path, as_attachment=True, download_name=download_name)
