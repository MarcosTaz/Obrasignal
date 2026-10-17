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
