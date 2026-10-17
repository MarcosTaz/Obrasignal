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
