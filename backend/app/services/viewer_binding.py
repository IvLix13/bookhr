"""Bind an unlinked viewer by the complete local name, without external calls."""
from app.extensions import db
from app.models import Employment, PersonNameHistory, User
from app.services.audit import log_audit


def normalized_full_name(value):
    # All name components must match; no initials, prefix or fuzzy matching.
    parts = (value or "").split()
    if len(parts) < 2 or any(len(part) == 1 or "." in part for part in parts):
        return None
    return " ".join(parts).casefold()


def auto_bind_viewer(user):
    """Stage one audited binding; caller owns the transaction. Never overwrite."""
    if user.role_name != "viewer" or not user.is_active or user.employment_id is not None:
        return False
    name = normalized_full_name(user.full_name)
    if not name:
        return False
    # Serialize concurrent logins/admin edits and re-read any existing binding.
    locked = User.query.filter_by(id=user.id).populate_existing().with_for_update().one()
    if locked.role_name != "viewer" or not locked.is_active or locked.employment_id is not None:
        return False
    if normalized_full_name(locked.full_name) != name:
        return False
    rows = db.session.query(Employment.id, PersonNameHistory.full_name).join(
        PersonNameHistory, PersonNameHistory.person_id == Employment.person_id
    ).filter(
        Employment.company_id == locked.company_id,
        Employment.status == "active",
        PersonNameHistory.valid_to.is_(None),
    ).all()
    names_by_employment = {}
    for employment_id, full_name in rows:
        names_by_employment.setdefault(employment_id, []).append(normalized_full_name(full_name))
    # Multiple open name-history rows are an inconsistency: don't choose one.
    candidates = [eid for eid, names in names_by_employment.items() if name in names]
    if len(candidates) != 1 or len(names_by_employment[candidates[0]]) != 1:
        return False
    locked.employment_id = candidates[0]
    log_audit("auto_bind", "user", locked.id,
              {"employment_id": None}, {"employment_id": candidates[0], "method": "full_name"})
    return True
