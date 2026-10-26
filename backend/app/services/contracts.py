"""Contract preparation, signing and effective periods. Read helpers never mutate."""
from datetime import timedelta, datetime, timezone
from sqlalchemy import select, or_, and_
from app.extensions import db
from app.models import Contract, ContractRenewal, Event, Employment, EventStatus, EmploymentStatus
from app.services.audit import log_audit
from app.utils.dates import today_moscow, add_years

class ContractConflict(ValueError):
    pass

def current_contract_query(employment_id=None):
    # Pending signed successors are effective even if the daily timer is late.
    pending = select(ContractRenewal.result_contract_id).where(
        ContractRenewal.result_contract_id.isnot(None), ContractRenewal.activated_at.is_(None))
    q = Contract.query.filter(or_(Contract.is_active.is_(True), and_(Contract.id.in_(pending), Contract.start_date <= today_moscow())))
    if employment_id is not None:
        q = q.filter(Contract.employment_id == employment_id)
    return q

def current_contract(employment):
    return current_contract_query(employment.id).order_by(Contract.end_date.desc(), Contract.id.desc()).first()

def lock_contract(contract_id):
    # Lock the employment first: signing successive future periods must use one lock order.
    employment_id = db.session.execute(select(Contract.employment_id).where(Contract.id == contract_id)).scalar_one_or_none()
    if employment_id is not None:
        db.session.execute(select(Employment.id).where(Employment.id == employment_id).with_for_update()).scalar_one()
    return db.session.execute(select(Contract).where(Contract.id == contract_id).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()

def renewal_for(contract_id):
    return ContractRenewal.query.filter_by(source_contract_id=contract_id).first()

def period(contract, term):
    start = contract.end_date + timedelta(days=1)
    return start, add_years(start, term) - timedelta(days=1)

def contract_context(event):
    if event.reference_type != "contract" or event.event_type not in {"report", "contract_signing"}:
        return None
    c = db.session.get(Contract, event.reference_id)
    r = renewal_for(c.id) if c else None
    linked = r and event.id in (r.report_event_id, r.signing_event_id)
    reason = None
    if not linked:
        reason = "Устаревшее мероприятие: откройте актуальный рапорт договора"
    elif event.event_type == "contract_signing" and not r.result_contract_id:
        report = db.session.get(Event, r.report_event_id)
        if not report or report.status != "completed" or not r.term_years:
            reason = "Сначала выполните подготовку рапорта и выберите срок договора"
    dates = period(c, r.term_years) if c and r and r.term_years else (None, None)
    return dict(stage="report" if event.event_type == "report" else "signing",
        source_contract_id=c.id if c else None, report_event_id=r.report_event_id if r else None,
        signing_event_id=r.signing_event_id if r else None, term_years=r.term_years if r else None,
        signing_date=c.end_date.isoformat() if c else None,
        new_start_date=dates[0].isoformat() if dates[0] else None,
        new_end_date=dates[1].isoformat() if dates[1] else None,
        result_contract_id=r.result_contract_id if r else None, blocked_reason=reason,
        reopen_blocked_reason="Договор уже подписан" if r and r.result_contract_id else None)

def lock_contract_event(event):
    if event.reference_type != "contract" or event.event_type not in {"report", "contract_signing"}:
        return event
    c = lock_contract(event.reference_id)
    if not c or c.employment_id != event.employment_id or c.employment.company_id != event.company_id:
        raise ContractConflict("Мероприятие ссылается на недоступный договор")
    db.session.refresh(event)  # refresh only after acquiring the common source lock
    if c.employment.status != EmploymentStatus.ACTIVE.value:
        raise ContractConflict("Сотрудник уволен")
    ctx = contract_context(event)
    if ctx and ctx["blocked_reason"]:
        raise ContractConflict(ctx["blocked_reason"])
    return event

def prepare(event, term, new_end_date=None):
    if new_end_date is not None:
        raise ValueError("Дата окончания рассчитывается при подписании")
    if term not in (1, 2, 3, 5):
        raise ValueError("Выберите срок нового договора: 1, 2, 3 или 5 лет")
    r = renewal_for(event.reference_id)
    if not r or r.report_event_id != event.id or r.result_contract_id:
        raise ContractConflict("Договор уже подписан или рапорт устарел")
    previous_term = r.term_years
    r.term_years = term
    log_audit("contract_report_prepare", "contract", event.reference_id,
              {"term_years": previous_term}, {"term_years": term, "event_id": event.id})

def sign(event, term=None, new_end_date=None):
    if term is not None or new_end_date is not None:
        raise ValueError("Срок нового договора задаётся в рапорте")
    c = db.session.get(Contract, event.reference_id)
    if not c or event.reference_type != "contract":
        raise ContractConflict("Подписание не связано с договором")
    r = renewal_for(c.id)
    if not r or r.signing_event_id != event.id:
        raise ContractConflict("Мероприятие подписания устарело")
    if r.result_contract_id:
        return db.session.get(Contract, r.result_contract_id)
    if r.source_end_date != c.end_date:
        raise ContractConflict("Дата договора изменилась, обновите мероприятие")
    start, end = period(c, r.term_years)
    result = Contract(employment_id=c.employment_id, start_date=start, end_date=end,
                      term_years=r.term_years, is_active=False)
    db.session.add(result)
    db.session.flush()
    r.result_contract_id = result.id
    log_audit("contract_sign", "contract", result.id, None,
              {"source_contract_id": c.id, "event_id": event.id, "term_years": r.term_years,
               "start_date": start.isoformat(), "end_date": end.isoformat()})
    activate_signed_contracts(c.employment)
    return result

def validate_reopen(event):
    ctx = contract_context(event)
    if ctx and ctx["reopen_blocked_reason"]:
        raise ContractConflict(ctx["reopen_blocked_reason"])

def activate_signed_contracts(employment):
    rows = ContractRenewal.query.join(Contract, Contract.id == ContractRenewal.source_contract_id).filter(
        Contract.employment_id == employment.id, ContractRenewal.result_contract_id.isnot(None),
        ContractRenewal.activated_at.is_(None)).all()
    for r in rows:
        result = db.session.get(Contract, r.result_contract_id)
        if result.start_date <= today_moscow():
            db.session.get(Contract, r.source_contract_id).is_active = False
            result.is_active = True
            r.activated_at = datetime.now(timezone.utc)

def rule_contracts(employment):
    current = current_contract(employment)
    ids = {current.id} if current else set()
    rows = ContractRenewal.query.join(Contract, Contract.id == ContractRenewal.source_contract_id).filter(
        Contract.employment_id == employment.id, ContractRenewal.result_contract_id.isnot(None)).all()
    for r in rows:
        ids.add(r.source_contract_id)  # preserve actual historical expiry and completed stages
        ids.add(r.result_contract_id)
    return Contract.query.filter(Contract.id.in_(ids)).all() if ids else []
