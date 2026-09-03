from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from lxml import etree
from signxml import XMLSigner, methods

from vertical_apps.industrial_claims.eidas_trusted_list_verifier import (
    EU_LOTL_URI,
    EidasTrustedListVerificationError,
    SignedEidasTrustedListVerifier,
)
from vertical_apps.industrial_claims.rfc3161_timestamp_provider import (
    EIDAS_GRANTED_STATUS,
    EIDAS_QTST_SERVICE_TYPE,
)


def _key_usage():
    return x509.KeyUsage(
        digital_signature=True,
        content_commitment=False,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=False,
        crl_sign=False,
        encipher_only=None,
        decipher_only=None,
    )


def _signer(name: str):
    now = datetime.now(timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=2))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(_key_usage(), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _tsa(name: str = "Synthetic qualified TSA"):
    now = datetime.now(timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=30))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def _der_b64(cert: x509.Certificate) -> str:
    return base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode("ascii")


def _sign(root: etree._Element, *, key, cert: x509.Certificate) -> bytes:
    signed = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha256",
        digest_algorithm="sha256",
    ).sign(root, key=key, cert=_pem(cert))
    return etree.tostring(signed, xml_declaration=True, encoding="UTF-8")


def _lotl(*, national_uri: str, national_signer: x509.Certificate, lotl_key, lotl_cert: x509.Certificate) -> bytes:
    now = datetime.now(timezone.utc)
    root = etree.Element("TrustServiceStatusList")
    scheme = etree.SubElement(root, "SchemeInformation")
    etree.SubElement(scheme, "TSLSequenceNumber").text = "389"
    etree.SubElement(scheme, "ListIssueDateTime").text = (now - timedelta(hours=1)).isoformat()
    next_update = etree.SubElement(scheme, "NextUpdate")
    etree.SubElement(next_update, "dateTime").text = (now + timedelta(days=30)).isoformat()
    pointers = etree.SubElement(scheme, "PointersToOtherTSL")
    pointer = etree.SubElement(pointers, "OtherTSLPointer")
    etree.SubElement(pointer, "TSLLocation").text = national_uri
    additional = etree.SubElement(pointer, "AdditionalInformation")
    etree.SubElement(additional, "SchemeTerritory").text = "ES"
    identities = etree.SubElement(pointer, "ServiceDigitalIdentities")
    identity = etree.SubElement(identities, "ServiceDigitalIdentity")
    digital_id = etree.SubElement(identity, "DigitalId")
    etree.SubElement(digital_id, "X509Certificate").text = _der_b64(national_signer)
    return _sign(root, key=lotl_key, cert=lotl_cert)


def _service_entry(
    parent: etree._Element,
    *,
    name: str,
    certificate: x509.Certificate,
    status: str,
    starts_at: datetime,
    history: bool = False,
) -> etree._Element:
    tag = "ServiceHistoryInstance" if history else "ServiceInformation"
    entry = etree.SubElement(parent, tag)
    etree.SubElement(entry, "ServiceTypeIdentifier").text = EIDAS_QTST_SERVICE_TYPE
    names = etree.SubElement(entry, "ServiceName")
    etree.SubElement(names, "Name").text = name
    identity = etree.SubElement(entry, "ServiceDigitalIdentity")
    digital_id = etree.SubElement(identity, "DigitalId")
    etree.SubElement(digital_id, "X509Certificate").text = _der_b64(certificate)
    etree.SubElement(entry, "ServiceStatus").text = status
    etree.SubElement(entry, "StatusStartingTime").text = starts_at.isoformat()
    return entry


def _national_tl(
    *,
    tsa: x509.Certificate,
    signer_key,
    signer_cert: x509.Certificate,
    current_status: str = EIDAS_GRANTED_STATUS,
    current_start: datetime | None = None,
    history_granted_start: datetime | None = None,
) -> bytes:
    now = datetime.now(timezone.utc)
    current_start = current_start or now - timedelta(days=20)
    root = etree.Element("TrustServiceStatusList")
    scheme = etree.SubElement(root, "SchemeInformation")
    etree.SubElement(scheme, "TSLSequenceNumber").text = "99"
    etree.SubElement(scheme, "ListIssueDateTime").text = (now - timedelta(hours=1)).isoformat()
    next_update = etree.SubElement(scheme, "NextUpdate")
    etree.SubElement(next_update, "dateTime").text = (now + timedelta(days=30)).isoformat()
    etree.SubElement(scheme, "SchemeTerritory").text = "ES"
    providers = etree.SubElement(root, "TrustServiceProviderList")
    provider = etree.SubElement(providers, "TrustServiceProvider")
    services = etree.SubElement(provider, "TSPServices")
    service = etree.SubElement(services, "TSPService")
    _service_entry(
        service,
        name="Synthetic qualified timestamp service",
        certificate=tsa,
        status=current_status,
        starts_at=current_start,
    )
    if history_granted_start is not None:
        history = etree.SubElement(service, "ServiceHistory")
        _service_entry(
            history,
            name="Synthetic qualified timestamp service",
            certificate=tsa,
            status=EIDAS_GRANTED_STATUS,
            starts_at=history_granted_start,
            history=True,
        )
    return _sign(root, key=signer_key, cert=signer_cert)


class _Response:
    def __init__(self, content: bytes, status: int = 200):
        self.content = content
        self.status_code = status
        self.is_redirect = False


class _Session:
    def __init__(self, mapping: dict[str, bytes]):
        self.mapping = dict(mapping)
        self.calls = []
    def get(self, uri, **kwargs):
        self.calls.append((uri, kwargs))
        if uri not in self.mapping:
            return _Response(b"missing", status=404)
        return _Response(self.mapping[uri])


def _fixture_chain(*, current_status=EIDAS_GRANTED_STATUS, current_start=None, history_granted_start=None, tl_signer_override=None):
    lotl_key, lotl_cert = _signer("Pinned EC LOTL signer")
    tl_key, tl_cert = _signer("National TL signer")
    tsa_key, tsa_cert = _tsa()
    national_uri = "https://trusted-list.example.test/ES.xml"
    lotl = _lotl(national_uri=national_uri, national_signer=tl_cert, lotl_key=lotl_key, lotl_cert=lotl_cert)
    sign_key, sign_cert = tl_signer_override if tl_signer_override is not None else (tl_key, tl_cert)
    tl = _national_tl(
        tsa=tsa_cert,
        signer_key=sign_key,
        signer_cert=sign_cert,
        current_status=current_status,
        current_start=current_start,
        history_granted_start=history_granted_start,
    )
    session = _Session({EU_LOTL_URI: lotl, national_uri: tl})
    verifier = SignedEidasTrustedListVerifier(
        territory="ES",
        lotl_signing_certificates_pem=(_pem(lotl_cert),),
        session=session,
    )
    return verifier, session, tsa_cert, lotl, tl, national_uri


def test_signed_lotl_to_member_state_tl_derives_qualified_receipt_for_exact_tsa():
    verifier, session, tsa, lotl, tl, national_uri = _fixture_chain()
    gen_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    evidence = verifier.verify(certificate=tsa, gen_time=gen_time)

    assert evidence.covers(certificate=tsa, gen_time=gen_time) is True
    assert evidence.territory == "ES"
    assert evidence.service_type == EIDAS_QTST_SERVICE_TYPE
    assert evidence.service_status == EIDAS_GRANTED_STATUS
    assert evidence.national_tl_uri == national_uri
    assert evidence.lotl_sha256 == __import__("hashlib").sha256(lotl).hexdigest()
    assert evidence.national_tl_sha256 == __import__("hashlib").sha256(tl).hexdigest()
    assert evidence.lotl_signer_certificate_sha256
    assert evidence.national_tl_signer_certificate_sha256
    assert session.calls[0][0] == EU_LOTL_URI
    assert session.calls[0][1]["allow_redirects"] is False


def test_tampering_member_state_status_after_signature_is_detected_before_service_use():
    verifier, session, tsa, _lotl, tl, national_uri = _fixture_chain()
    session.mapping[national_uri] = tl.replace(b"Svcstatus/granted", b"Svcstatus/withdrawn")
    with pytest.raises(EidasTrustedListVerificationError, match="XMLDSig verification failed"):
        verifier.verify(certificate=tsa, gen_time=datetime.now(timezone.utc) - timedelta(minutes=1))


def test_lotl_pointer_signer_substitution_cannot_authorize_different_national_tl_signer():
    rogue_key, rogue_cert = _signer("Rogue national signer")
    verifier, _session, tsa, _lotl, _tl, _uri = _fixture_chain(tl_signer_override=(rogue_key, rogue_cert))
    with pytest.raises(EidasTrustedListVerificationError, match="XMLDSig verification failed"):
        verifier.verify(certificate=tsa, gen_time=datetime.now(timezone.utc) - timedelta(minutes=1))


def test_service_history_is_evaluated_at_token_time_not_current_status():
    now = datetime.now(timezone.utc)
    withdrawn_start = now - timedelta(days=1)
    granted_start = now - timedelta(days=10)
    verifier, _session, tsa, _lotl, _tl, _uri = _fixture_chain(
        current_status="http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/withdrawn",
        current_start=withdrawn_start,
        history_granted_start=granted_start,
    )
    historical = now - timedelta(days=5)
    evidence = verifier.verify(certificate=tsa, gen_time=historical)
    assert evidence.covers(certificate=tsa, gen_time=historical) is True
    assert evidence.service_valid_until == withdrawn_start.isoformat()

    with pytest.raises(EidasTrustedListVerificationError, match="not uniquely covered"):
        verifier.verify(certificate=tsa, gen_time=now)


def test_different_tsa_certificate_cannot_borrow_another_service_qualification():
    verifier, _session, existing_tsa, _lotl, _tl, _uri = _fixture_chain()
    assert existing_tsa is not None
    _key, different_tsa = _tsa("Different TSA")
    with pytest.raises(EidasTrustedListVerificationError, match="exact TSA certificate"):
        verifier.verify(certificate=different_tsa, gen_time=datetime.now(timezone.utc) - timedelta(minutes=1))
