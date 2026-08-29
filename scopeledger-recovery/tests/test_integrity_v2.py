import os, tempfile, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DB = Path(tempfile.mkdtemp())/'scopeledger-test.db'
os.environ['SCOPELEDGER_DB']=str(DB)

from fastapi.testclient import TestClient
from app.main import app
from app.core import db, sha256_text, password_hash, utcnow, audit

client=TestClient(app)
TOKEN='test-session-token'
CSRF='csrf-test-token'
HEAD={'X-CSRF-Token':CSRF}


def seed_owner(email='owner@example.com'):
    with db() as c:
        c.execute('INSERT INTO organizations(name,created_at) VALUES(?,?)',('Acme ERP',utcnow())); oid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
        c.execute('INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)',(email,password_hash('correct-horse-battery-staple'),utcnow())); uid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
        c.execute("INSERT INTO memberships(organization_id,user_id,role) VALUES(?,?, 'OWNER')",(oid,uid))
        c.execute('INSERT INTO sessions(token_hash,user_id,organization_id,csrf_token,expires_at,created_at) VALUES(?,?,?,?,?,?)',(sha256_text(TOKEN),uid,oid,CSRF,9999999999,utcnow()))
    client.cookies.set('scopeledger_session',TOKEN)
    return oid,uid


def post(path,data=None,files=None):
    return client.post(path,data=data or {},files=files,headers=HEAD)


def make_reviewed_candidate(classification='OUT_OF_SCOPE_CONFIRMED'):
    p=post('/projects',{'name':'ERP Rollout','contract_value':'100000','target_margin':'35','hourly_cost':'55'}); assert p.status_code==200,p.text; pid=p.json()['id']
    assert post(f'/projects/{pid}/scope',{'kind':'EXCLUDED','title':'France business unit','description':'Excluded unless separately approved'}).status_code==200
    assert post(f'/projects/{pid}/baseline/confirm').status_code==200
    e=post(f'/projects/{pid}/events',{'external_id':'REQ-1','event_type':'CLIENT_REQUEST','text':'Please add France business unit rollout','hours':'0','delay_days':'0'}); assert e.status_code==200,e.text; cid=e.json()['candidate_id']
    d=post(f'/projects/{pid}/events',{'external_id':'DEL-1','event_type':'DELIVERY','text':'France business unit implementation completed','hours':'35','delay_days':'0'}); assert d.status_code==200,d.text
    r=post(f'/candidates/{cid}/review',{'classification':classification}); assert r.status_code==200,r.text
    return pid,cid


def approve_candidate(cid,amount=3000):
    pr=post(f'/candidates/{cid}/proposal',{'amount':str(amount),'timeline_days':'0','description':'France rollout change'}); assert pr.status_code==200,pr.text
    ar=post(f'/candidates/{cid}/approval-requests',{'intended_respondent_name':'Demo client','intended_respondent_email':'client@example.com','expires_in_hours':'72','identity_mode':'TOKEN_EMAIL'}); assert ar.status_code==200,ar.text
    token=ar.json()['token']
    rr=client.post(f'/approve/{token}',data={'decision':'APPROVE','respondent_name':'Client','respondent_email':'client@example.com','note':''}); assert rr.status_code==200,rr.text
    return ar.json()


def setup_module(module):
    seed_owner()


def test_baseline_conflict_fails_closed():
    p=post('/projects',{'name':'Conflict','contract_value':'1','target_margin':'10','hourly_cost':'1'}); pid=p.json()['id']
    post(f'/projects/{pid}/scope',{'kind':'INCLUDED','title':'Data migration'})
    post(f'/projects/{pid}/scope',{'kind':'EXCLUDED','title':' data migration '})
    r=post(f'/projects/{pid}/baseline/confirm')
    assert r.status_code==409


def test_in_scope_cannot_be_proposed():
    _,cid=make_reviewed_candidate('IN_SCOPE')
    r=post(f'/candidates/{cid}/proposal',{'amount':'100','timeline_days':'0','description':'Should not commercialize'})
    assert r.status_code==409


def test_request_changes_requires_new_proposal_version():
    _,cid=make_reviewed_candidate()
    post(f'/candidates/{cid}/proposal',{'amount':'3000','timeline_days':'0','description':'v1'})
    ar=post(f'/candidates/{cid}/approval-requests',{'intended_respondent_name':'Client','intended_respondent_email':'client@example.com','expires_in_hours':'72','identity_mode':'TOKEN_EMAIL'}); token=ar.json()['token']
    rr=client.post(f'/approve/{token}',data={'decision':'REQUEST_CHANGES','respondent_name':'Client','respondent_email':'client@example.com','note':'Reduce price'}); assert rr.status_code==200
    stale=post(f'/candidates/{cid}/approval-requests',{'intended_respondent_name':'Client','intended_respondent_email':'client@example.com','expires_in_hours':'72','identity_mode':'TOKEN_EMAIL'})
    assert stale.status_code==409
    assert post(f'/candidates/{cid}/proposal',{'amount':'2500','timeline_days':'0','description':'v2'}).status_code==200
    fresh=post(f'/candidates/{cid}/approval-requests',{'intended_respondent_name':'Client','intended_respondent_email':'client@example.com','expires_in_hours':'72','identity_mode':'TOKEN_EMAIL'})
    assert fresh.status_code==200,fresh.text


def test_expired_approval_persists_expired_state():
    _,cid=make_reviewed_candidate(); ar=approve_candidate.__wrapped__ if False else None
    post(f'/candidates/{cid}/proposal',{'amount':'3000','timeline_days':'0','description':'expiry'})
    r=post(f'/candidates/{cid}/approval-requests',{'intended_respondent_name':'Client','intended_respondent_email':'expire@example.com','expires_in_hours':'1','identity_mode':'TOKEN_EMAIL'}); token=r.json()['token']; rid=r.json()['id']
    with db() as c:c.execute('UPDATE approval_requests SET expires_at=0 WHERE id=?',(rid,))
    view=client.get(f'/approve/{token}'); assert view.status_code==410
    with db() as c: row=c.execute('SELECT status FROM approval_requests WHERE id=?',(rid,)).fetchone()
    assert row['status']=='EXPIRED'


def test_concurrent_sow_is_idempotent():
    p=post('/projects',{'name':'SOW Race','contract_value':'10','target_margin':'20','hourly_cost':'1'}); pid=p.json()['id']
    def one(_):
        with TestClient(app) as c:
            c.cookies.set('scopeledger_session',TOKEN)
            return c.post(f'/projects/{pid}/sow',headers=HEAD,files={'file':('sow.txt',b'France business unit excluded.','text/plain')})
    with ThreadPoolExecutor(max_workers=6) as ex: rs=list(ex.map(one,range(6)))
    assert all(r.status_code==200 for r in rs),[(r.status_code,r.text) for r in rs]
    assert sum(1 for r in rs if not r.json()['duplicate'])==1
    with db() as c: n=c.execute('SELECT COUNT(*) FROM documents WHERE project_id=?',(pid,)).fetchone()[0]
    assert n==1


def test_concurrent_jira_cumulative_is_monotonic_and_non_additive():
    p=post('/projects',{'name':'Jira Race','contract_value':'10','target_margin':'20','hourly_cost':'1'}); pid=p.json()['id']
    post(f'/projects/{pid}/scope',{'kind':'EXCLUDED','title':'France rollout'}); post(f'/projects/{pid}/baseline/confirm')
    vals=[5,10,7,15,12,15]
    def one(v):
        with TestClient(app) as c:
            c.cookies.set('scopeledger_session',TOKEN)
            return c.post(f'/projects/{pid}/jira',headers=HEAD,data={'issue_key':'ERP-42','summary':'France rollout implementation','cumulative_hours':str(v)})
    with ThreadPoolExecutor(max_workers=6) as ex: rs=list(ex.map(one,vals))
    assert all(r.status_code==200 for r in rs),[(r.status_code,r.text) for r in rs]
    with db() as c:
        floor=c.execute('SELECT counted_hours FROM jira_snapshots WHERE project_id=? AND issue_key=?',(pid,'ERP-42')).fetchone()[0]
        total=c.execute("SELECT COALESCE(SUM(hours),0) FROM events WHERE project_id=? AND event_type='JIRA'",(pid,)).fetchone()[0]
    assert floor==15
    assert abs(total-15)<1e-9


def _ready_for_money():
    _,cid=make_reviewed_candidate(); approve_candidate(cid)
    assert post(f'/candidates/{cid}/billing-handoff',{'handoff_ref':'BILL-1'}).status_code==200
    return cid


def test_concurrent_invoice_same_is_idempotent_and_conflict_is_immutable():
    cid=_ready_for_money()
    def one(_):
        with TestClient(app) as c:
            c.cookies.set('scopeledger_session',TOKEN)
            return c.post(f'/candidates/{cid}/invoice',headers=HEAD,data={'invoice_ref':'INV-1','amount':'3000','invoice_date':'2026-08-28'})
    with ThreadPoolExecutor(max_workers=5) as ex: rs=list(ex.map(one,range(5)))
    assert all(r.status_code==200 for r in rs),[(r.status_code,r.text) for r in rs]
    assert sum(1 for r in rs if not r.json().get('duplicate'))==1
    bad=post(f'/candidates/{cid}/invoice',{'invoice_ref':'INV-CHANGED','amount':'3000','invoice_date':'2026-08-28'})
    assert bad.status_code==409


def test_concurrent_payments_do_not_lose_updates():
    cid=_ready_for_money(); assert post(f'/candidates/{cid}/invoice',{'invoice_ref':'INV-PAY','amount':'3000','invoice_date':'2026-08-28'}).status_code==200
    vals=[('PAY-1',1000),('PAY-2',1000),('PAY-3',1000)]
    def one(x):
        ext,amt=x
        with TestClient(app) as c:
            c.cookies.set('scopeledger_session',TOKEN)
            return c.post(f'/candidates/{cid}/payments',headers=HEAD,data={'external_id':ext,'amount':str(amt),'payment_date':'2026-08-29'})
    with ThreadPoolExecutor(max_workers=3) as ex: rs=list(ex.map(one,vals))
    assert all(r.status_code==200 for r in rs),[(r.status_code,r.text) for r in rs]
    with db() as c:
        paid=c.execute('SELECT paid_amount FROM billing WHERE candidate_id=?',(cid,)).fetchone()[0]
        rows=c.execute('SELECT COALESCE(SUM(amount),0),COUNT(*) FROM payments WHERE candidate_id=?',(cid,)).fetchone()
        state=c.execute('SELECT state FROM candidates WHERE id=?',(cid,)).fetchone()[0]
    assert paid==3000 and rows[0]==3000 and rows[1]==3 and state=='PAID'


def test_payment_cannot_precede_invoice():
    cid=_ready_for_money(); post(f'/candidates/{cid}/invoice',{'invoice_ref':'INV-DATE','amount':'3000','invoice_date':'2026-08-28'})
    r=post(f'/candidates/{cid}/payments',{'external_id':'EARLY','amount':'100','payment_date':'2026-08-27'})
    assert r.status_code==409


def _seed_second_tenant(email='owner-b@example.com', role='OWNER'):
    token='tenant-b-session-token'; csrf='csrf-tenant-b'
    with db() as c:
        c.execute('INSERT INTO organizations(name,created_at) VALUES(?,?)',('Beta Integrators',utcnow())); oid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
        c.execute('INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)',(email,password_hash('correct-horse-battery-staple'),utcnow())); uid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
        c.execute('INSERT INTO memberships(organization_id,user_id,role) VALUES(?,?,?)',(oid,uid,role))
        c.execute('INSERT INTO sessions(token_hash,user_id,organization_id,csrf_token,expires_at,created_at) VALUES(?,?,?,?,?,?)',(sha256_text(token),uid,oid,csrf,9999999999,utcnow()))
    return oid,uid,token,csrf


def _client_for(token, csrf):
    c=TestClient(app); c.cookies.set('scopeledger_session',token); return c,{'X-CSRF-Token':csrf}


def test_tenant_isolation_hides_and_blocks_foreign_project():
    p=post('/projects',{'name':'Tenant A Secret','contract_value':'50000','target_margin':'30','hourly_cost':'80'}); assert p.status_code==200; pid=p.json()['id']
    oid_b,uid_b,tok_b,csrf_b=_seed_second_tenant()
    c,h=_client_for(tok_b,csrf_b)
    listing=c.get('/projects'); assert listing.status_code==200 and all(x['id']!=pid for x in listing.json())
    assert c.get(f'/projects/{pid}').status_code==404
    assert c.post(f'/projects/{pid}/scope',headers=h,data={'kind':'EXCLUDED','title':'Foreign mutation'}).status_code==404
    with db() as d: assert d.execute('SELECT COUNT(*) FROM scope_items WHERE project_id=? AND title=?',(pid,'Foreign mutation')).fetchone()[0]==0


def test_rbac_owner_reviewer_analyst_boundaries():
    p=post('/projects',{'name':'RBAC','contract_value':'100','target_margin':'20','hourly_cost':'5'}); pid=p.json()['id']
    with db() as d:
        oid=d.execute('SELECT organization_id FROM projects WHERE id=?',(pid,)).fetchone()[0]
        creds=[]
        for role,email in [('COMMERCIAL_REVIEWER','reviewer@example.com'),('ANALYST','analyst@example.com')]:
            tok=f'{role.lower()}-token'; csrf=f'{role.lower()}-csrf'
            d.execute('INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)',(email,password_hash('correct-horse-battery-staple'),utcnow())); uid=d.execute('SELECT last_insert_rowid()').fetchone()[0]
            d.execute('INSERT INTO memberships(organization_id,user_id,role) VALUES(?,?,?)',(oid,uid,role))
            d.execute('INSERT INTO sessions(token_hash,user_id,organization_id,csrf_token,expires_at,created_at) VALUES(?,?,?,?,?,?)',(sha256_text(tok),uid,oid,csrf,9999999999,utcnow())); creds.append((role,tok,csrf))
    rc,rh=_client_for(creds[0][1],creds[0][2]); ac,ah=_client_for(creds[1][1],creds[1][2])
    assert rc.post('/projects',headers=rh,data={'name':'Forbidden'}).status_code==403
    assert rc.post(f'/projects/{pid}/scope',headers=rh,data={'kind':'EXCLUDED','title':'Reviewer scope'}).status_code==200
    assert ac.post(f'/projects/{pid}/scope',headers=ah,data={'kind':'EXCLUDED','title':'Analyst mutation'}).status_code==403
    got=ac.get(f'/projects/{pid}'); assert got.status_code==200 and 'candidates' not in got.json() and 'contract_value' not in got.json()['project']
    assert ac.get('/team').status_code==403


def test_csrf_and_origin_fail_closed():
    assert client.post('/projects',data={'name':'No CSRF'}).status_code==403
    assert client.post('/projects',headers={'X-CSRF-Token':CSRF,'Sec-Fetch-Site':'cross-site'},data={'name':'Cross Site'}).status_code==403
    assert client.post('/projects',headers={'X-CSRF-Token':CSRF,'Origin':'https://evil.example','Host':'scopeledger.example'},data={'name':'Bad Origin'}).status_code==403


def test_role_change_revokes_existing_member_session():
    p=post('/projects',{'name':'Session revoke','contract_value':'1','target_margin':'1','hourly_cost':'1'}); pid=p.json()['id']
    with db() as d:
        oid=d.execute('SELECT organization_id FROM projects WHERE id=?',(pid,)).fetchone()[0]
        d.execute('INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)',('revoked@example.com',password_hash('correct-horse-battery-staple'),utcnow())); uid=d.execute('SELECT last_insert_rowid()').fetchone()[0]
        d.execute("INSERT INTO memberships(organization_id,user_id,role) VALUES(?,?,'COMMERCIAL_REVIEWER')",(oid,uid))
        tok='revoked-session'; csrf='revoked-csrf'; d.execute('INSERT INTO sessions(token_hash,user_id,organization_id,csrf_token,expires_at,created_at) VALUES(?,?,?,?,?,?)',(sha256_text(tok),uid,oid,csrf,9999999999,utcnow()))
    c,h=_client_for(tok,csrf); assert c.get('/me').status_code==200
    r=post(f'/team/{uid}/role',{'role':'ANALYST'}); assert r.status_code==200 and r.json()['sessions_revoked'] is True
    assert c.get('/me').status_code==401


def test_approval_replay_and_identity_lockout_are_fail_closed():
    _,cid=make_reviewed_candidate(); post(f'/candidates/{cid}/proposal',{'amount':'3000','timeline_days':'0','description':'identity'})
    ar=post(f'/candidates/{cid}/approval-requests',{'intended_respondent_name':'Client','intended_respondent_email':'identity@example.com','expires_in_hours':'72','identity_mode':'TOKEN_EMAIL'}); assert ar.status_code==200; token=ar.json()['token']; rid=ar.json()['id']
    for i in range(4):
        bad=client.post(f'/approve/{token}',data={'decision':'APPROVE','respondent_name':'Attacker','respondent_email':f'wrong{i}@example.com'}); assert bad.status_code==403
    locked=client.post(f'/approve/{token}',data={'decision':'APPROVE','respondent_name':'Attacker','respondent_email':'wrong4@example.com'}); assert locked.status_code==423
    assert client.post(f'/approve/{token}',data={'decision':'APPROVE','respondent_name':'Client','respondent_email':'identity@example.com'}).status_code==410
    with db() as d:
        row=d.execute('SELECT status,identity_failure_count FROM approval_requests WHERE id=?',(rid,)).fetchone(); state=d.execute('SELECT state FROM candidates WHERE id=?',(cid,)).fetchone()[0]
    assert row['status']=='IDENTITY_LOCKED' and row['identity_failure_count']==5 and state=='CHANGE_DRAFT'
    post(f'/candidates/{cid}/proposal',{'amount':'2900','timeline_days':'0','description':'identity v2'})
    fresh=post(f'/candidates/{cid}/approval-requests',{'intended_respondent_name':'Client','intended_respondent_email':'identity@example.com','expires_in_hours':'72','identity_mode':'TOKEN_EMAIL'}); assert fresh.status_code==200; t2=fresh.json()['token']
    ok=client.post(f'/approve/{t2}',data={'decision':'APPROVE','respondent_name':'Client','respondent_email':'identity@example.com'}); assert ok.status_code==200
    replay=client.post(f'/approve/{t2}',data={'decision':'APPROVE','respondent_name':'Client','respondent_email':'identity@example.com'}); assert replay.status_code==410


def test_audit_and_evidence_pack_redact_secret_material():
    _,cid=make_reviewed_candidate(); approve_candidate(cid)
    with db() as d:
        pid=d.execute('SELECT project_id FROM candidates WHERE id=?',(cid,)).fetchone()[0]
        oid=d.execute('SELECT organization_id FROM projects WHERE id=?',(pid,)).fetchone()[0]
        audit(d,oid,pid,'SYSTEM','test','SECRET_TEST',{'token':'super-secret-token','password':'pw','nested':{'verification_code':'123456','safe':'keep'}})
    pack=client.get(f'/candidates/{cid}/evidence-pack'); assert pack.status_code==200
    raw=pack.text
    assert 'super-secret-token' not in raw and '123456' not in raw and '"password":"pw"' not in raw
    assert '[REDACTED]' in raw and 'keep' in raw
