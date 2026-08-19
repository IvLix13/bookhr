"""Repair stored contract dates to match PR #28 invariants."""

from __future__ import annotations

from dataclasses import dataclass

from app.extensions import db
from app.models import Contract
from app.services.employees import deactivate_other_active_contracts
from app.utils.dates import calculate_contract_start


@dataclass(frozen=True)
class RepairContractsResult:
    contracts_seen: int
    start_dates_fixed: int
    duplicates_deactivated: int
    skipped_missing_term: int


def repair_active_contract_dates() -> RepairContractsResult:
    """Reconcile active contracts: start = end - term, one active contract per employment."""
    contracts_seen = 0
    start_dates_fixed = 0
    duplicates_deactivated = 0
    skipped_missing_term = 0

    active_by_employment: dict[int, list[Contract]] = {}
    for contract in Contract.query.filter_by(is_active=True).order_by(Contract.id).all():
        contracts_seen += 1
        active_by_employment.setdefault(contract.employment_id, []).append(contract)

    for employment_id, contracts in active_by_employment.items():
        keep = max(contracts, key=lambda item: (item.end_date, item.id))
        duplicates_deactivated += deactivate_other_active_contracts(
            employment_id,
            keep_contract_id=keep.id,
        )

        if keep.term_years is None or keep.term_years <= 0:
            skipped_missing_term += 1
            continue

        expected_start = calculate_contract_start(keep.end_date, keep.term_years)
        if keep.start_date != expected_start:
            keep.start_date = expected_start
            start_dates_fixed += 1

    db.session.commit()
    return RepairContractsResult(
        contracts_seen=contracts_seen,
        start_dates_fixed=start_dates_fixed,
        duplicates_deactivated=duplicates_deactivated,
        skipped_missing_term=skipped_missing_term,
    )
