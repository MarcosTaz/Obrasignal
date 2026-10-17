"""Staging-only HTTP contract for verified Neon company access.

Not registered by production app. A caller injects a trusted verifier and
server-owned membership connection factory. No application secret or database
URL is read here.
"""
from flask import Blueprint, jsonify, request
from jwt import InvalidTokenError
from auth_context_jwt import JwksUnavailableError
import psycopg
from neon_company_access import authorize_company, lookup_neon_membership, CompanyAccessDenied

def build_neon_company_probe(verifier, connection_factory):
    blueprint = Blueprint("neon_company_probe", __name__)

    @blueprint.get("/__staging/neon/companies/<company_id>/access")
    def probe(company_id):
        scheme, separator, bearer = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not separator or not bearer.strip():
            return jsonify(error="unauthorized"), 401
        try:
            identity = verifier.verify(bearer.strip())
            claims = getattr(identity, "claims", None)
            issuer = claims.get("iss") if isinstance(claims, dict) else None
            subject = getattr(identity, "subject", None)
            if not isinstance(issuer, str) or not issuer.strip() or not isinstance(subject, str) or not subject.strip():
                raise InvalidTokenError("verified identity missing required claims")
            with connection_factory() as connection:
                permitted = authorize_company(
                    issuer, subject, company_id,
                    lambda i, s, c: lookup_neon_membership(connection, i, s, c),
                )
        except InvalidTokenError:
            return jsonify(error="unauthorized"), 401
        except CompanyAccessDenied:
            return jsonify(error="forbidden"), 403
        except (JwksUnavailableError, psycopg.Error):
            # Staging must fail closed without disclosing provider/database details.
            return jsonify(error="authorization_service_unavailable"), 503
        return jsonify(company_id=permitted, authorized=True), 200

    return blueprint
