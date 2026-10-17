"""Company membership gate for staged identity migration."""
from dataclasses import dataclass

class CompanyAccessDenied(PermissionError):
    pass

@dataclass(frozen=True)
class Membership:
    issuer: str
    subject: str
    company_id: str
    active: bool

def authorize_company(issuer, subject, company_id, lookup):
    if not all(isinstance(x, str) and x.strip() for x in (issuer, subject, company_id)):
        raise CompanyAccessDenied("unauthorized_company")
    member = lookup(issuer, subject, company_id)
    if not isinstance(member, Membership) or not member.active:
        raise CompanyAccessDenied("unauthorized_company")
    if (member.issuer, member.subject, member.company_id) != (issuer, subject, company_id):
        raise CompanyAccessDenied("unauthorized_company")
    return company_id


def lookup_neon_membership(connection, issuer, subject, company_id):
    """Read membership from Neon Better Auth using bound parameters only.

    Connection is server-owned. Callers must provide a verified JWT subject;
    never expose database credentials or accept a caller-provided connection.
    """
    from uuid import UUID
    try:
        user_id = UUID(subject)
        organization_id = UUID(company_id)
    except (TypeError, ValueError, AttributeError):
        return None
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT 1 FROM neon_auth.member '
            'WHERE "userId" = %s AND "organizationId" = %s LIMIT 1',
            (user_id, organization_id),
        )
        found = cursor.fetchone()
    if not found:
        return None
    return Membership(issuer=issuer, subject=subject, company_id=company_id, active=True)
