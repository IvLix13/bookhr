from datetime import date
import pytest
from app.extensions import db
from app.models import Contract, ContractRenewal, Event, Employment
from app.services.employees import create_person_with_employment, get_active_contract
from app.services.rule_engine import recalculate_employment_events, run_rule_engine

@pytest.fixture()
def cycle(hr_client, seed_company):
    with hr_client.application.app_context():
        _, e = create_person_with_employment(company_id=seed_company.id, full_name="Подписание Тест", hire_date=date(2020,1,1), title="Инженер")
        c = Contract(employment_id=e.id, start_date=date(2025,12,1), end_date=date(2027,11,30), term_years=2, is_active=True)
        db.session.add(c)
        db.session.flush()
        recalculate_employment_events(e)
        db.session.commit()
        r = ContractRenewal.query.filter_by(source_contract_id=c.id).one()
        return c.id, e.id, r.report_event_id, r.signing_event_id

def complete(client, event, **payload):
    return client.post(f"/api/events/{event}/complete", json=payload)

def test_report_signing_idempotency_and_history(hr_client, cycle):
    cid, eid, report, signing = cycle
    assert complete(hr_client, signing).status_code == 409
    for _ in range(2):
        assert complete(hr_client, report, extension_term_years=3).status_code == 200
    assert complete(hr_client, report, extension_term_years=2).status_code == 409
    with hr_client.application.app_context():
        c = db.session.get(Contract, cid)
        assert (c.start_date,c.end_date,c.term_years) == (date(2025,12,1),date(2027,11,30),2)
    for _ in range(2):
        assert complete(hr_client, signing).status_code == 200
    with hr_client.application.app_context():
        r = ContractRenewal.query.filter_by(source_contract_id=cid).one()
        result = db.session.get(Contract,r.result_contract_id)
        assert (result.start_date,result.end_date,result.term_years)==(date(2027,12,1),date(2030,11,30),3)
        assert Contract.query.filter_by(employment_id=eid).count()==2
        assert get_active_contract(db.session.get(Employment,eid)).id==cid
        assert db.session.get(Contract,cid).is_active
        assert Event.query.filter_by(event_type='contract', reference_id=cid).count() == 0
    for event in (report,signing):
        assert hr_client.post(f'/api/events/{event}/reopen',json={}).status_code==409
    assert complete(hr_client,signing,extension_term_years=5).status_code==400

@pytest.mark.parametrize('term',[None,0,-1,4,'NaN','Infinity'])
def test_invalid_report_does_not_complete(hr_client,cycle,term):
    _,_,report,_=cycle
    assert complete(hr_client,report,extension_term_years=term).status_code==400
    with hr_client.application.app_context():
        assert db.session.get(Event,report).status!='completed'

def test_reopen_and_edit_preserves_term(hr_client,cycle):
    cid,_,report,signing=cycle
    assert complete(hr_client,report,extension_term_years=3).status_code==200
    assert hr_client.patch(f'/api/contracts/{cid}',json={'end_date':'2028-02-29','term_years':2}).status_code==200
    with hr_client.application.app_context():
        r=ContractRenewal.query.filter_by(source_contract_id=cid).one()
        assert r.term_years==3 and r.report_event_id==report
        assert db.session.get(Event,signing).event_date==date(2028,2,29)
    assert hr_client.post(f'/api/events/{report}/reopen',json={}).status_code==200
    assert complete(hr_client,signing).status_code==409
    assert complete(hr_client,report,extension_term_years=5).status_code==200
    assert complete(hr_client,signing).status_code==200
    with hr_client.application.app_context():
        r=ContractRenewal.query.filter_by(source_contract_id=cid).one()
        c=db.session.get(Contract,r.result_contract_id)
        assert (c.start_date,c.end_date)==(date(2028,3,1),date(2033,2,28))

def test_timer_late_read_and_activation(hr_client,cycle,monkeypatch):
    cid,eid,report,signing=cycle
    assert complete(hr_client,report,extension_term_years=1).status_code==200
    assert complete(hr_client,signing).status_code==200
    monkeypatch.setattr('app.services.contracts.today_moscow',lambda:date(2027,12,1))
    with hr_client.application.app_context():
        r=ContractRenewal.query.filter_by(source_contract_id=cid).one()
        result_id=r.result_contract_id
        assert get_active_contract(db.session.get(Employment,eid)).id==result_id
        assert not db.session.get(Contract,result_id).is_active
    data=hr_client.get('/api/contracts').get_json()['data']['items']
    assert [c['id'] for c in data]==[result_id]
    with hr_client.application.app_context():
        run_rule_engine()
        db.session.commit()
        assert db.session.get(Contract,result_id).is_active
        assert not db.session.get(Contract,cid).is_active

def test_legacy_completed_not_inferred(hr_client,cycle):
    cid,_,report,signing=cycle
    with hr_client.application.app_context():
        db.session.get(Event,report).status='completed'
        db.session.commit()
        run_rule_engine()
        db.session.commit()
        assert ContractRenewal.query.filter_by(source_contract_id=cid).one().term_years is None
    assert complete(hr_client,signing).status_code==409
    assert hr_client.post(f'/api/events/{report}/reopen',json={}).status_code==200
    assert complete(hr_client,report,extension_term_years=1).status_code==200
    assert complete(hr_client,signing).status_code==200

def test_override_rejected(hr_client,cycle):
    _,_,report,signing=cycle
    assert complete(hr_client,report,extension_term_years=3,new_end_date='2030-01-01').status_code==400
    assert complete(hr_client,report,extension_term_years=3).status_code==200
    assert complete(hr_client,signing,new_end_date='2030-01-01').status_code==400

@pytest.mark.parametrize('end,term,start,expected',[
    (date(2026,11,30),3,date(2026,12,1),date(2029,11,30)),
    (date(2028,2,28),1,date(2028,2,29),date(2029,2,27)),
    (date(2028,2,29),2,date(2028,3,1),date(2030,2,28)),
    (date(2026,12,31),5,date(2027,1,1),date(2031,12,31)),
])
def test_inclusive_period_boundaries(end,term,start,expected):
    from app.services.contracts import period
    from types import SimpleNamespace
    assert period(SimpleNamespace(end_date=end),term)==(start,expected)


def test_viewer_cannot_prepare_or_sign(cycle,viewer_client):
    _,_,report,signing=cycle
    assert complete(viewer_client,report,extension_term_years=3).status_code==403
    assert complete(viewer_client,signing).status_code==403
