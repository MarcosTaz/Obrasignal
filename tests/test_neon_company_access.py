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
