from neon_company_access import Membership, CompanyAccessDenied, authorize_company


def test_allowed():
    member = Membership('neon', 'user1', 'org1', True)
    assert authorize_company('neon', 'user1', 'org1', lambda *_: member) == 'org1'


def test_denied():
    member = Membership('neon', 'user2', 'org1', True)
    try:
        authorize_company('neon', 'user1', 'org1', lambda *_: member)
    except CompanyAccessDenied:
        return
    raise AssertionError('cross-identity access was accepted')


def test_missing_membership_denied():
    try:
        authorize_company('neon', 'user1', 'org1', lambda *_: None)
    except CompanyAccessDenied:
        return
    raise AssertionError('missing membership was accepted')


def test_inactive_membership_denied():
    member = Membership('neon', 'user1', 'org1', False)
    try:
        authorize_company('neon', 'user1', 'org1', lambda *_: member)
    except CompanyAccessDenied:
        return
    raise AssertionError('inactive membership was accepted')


def test_wrong_company_denied():
    member = Membership('neon', 'user1', 'org2', True)
    try:
        authorize_company('neon', 'user1', 'org1', lambda *_: member)
    except CompanyAccessDenied:
        return
    raise AssertionError('cross-company membership was accepted')


def test_sql_lookup_uses_bound_ids_and_requires_membership():
    from uuid import UUID
    from neon_company_access import lookup_neon_membership
    class Cursor:
        def __init__(self, present):
            self.present = present
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def execute(self, sql, params):
            assert 'neon_auth.member' in sql
            assert '%s' in sql
            assert len(params) == 2
            assert all(isinstance(x, UUID) for x in params)
        def fetchone(self):
            return (1,) if self.present else None
    class Connection:
        def __init__(self, present):
            self.present = present
        def cursor(self):
            return Cursor(self.present)
    user = '11111111-1111-4111-8111-111111111111'
    company = '22222222-2222-4222-8222-222222222222'
    good = lambda i, s, c: lookup_neon_membership(Connection(True), i, s, c)
    missing = lambda i, s, c: lookup_neon_membership(Connection(False), i, s, c)
    assert authorize_company('neon', user, company, good) == company
    try:
        authorize_company('neon', user, company, missing)
    except CompanyAccessDenied:
        pass
    else:
        raise AssertionError('missing persisted membership accepted')
    assert lookup_neon_membership(Connection(True), 'neon', 'invalid-id', company) is None
