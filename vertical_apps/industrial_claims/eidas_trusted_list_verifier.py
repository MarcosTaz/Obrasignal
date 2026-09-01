from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence
from urllib.parse import urlparse

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from lxml import etree
from signxml import SignatureConfiguration, XMLVerifier

from vertical_apps.industrial_claims.rfc3161_timestamp_provider import (
    EIDAS_CHAIN_VERIFICATION_METHOD,
    EIDAS_GRANTED_STATUS,
    EIDAS_QTST_SERVICE_TYPE,
    EidasQualifiedTimestampEvidence,
)


EU_LOTL_URI = "https://ec.europa.eu/tools/lotl/eu-lotl.xml"
MAX_TRUSTED_LIST_BYTES = 32 * 1024 * 1024
DEFAULT_TIMEOUT = (4.0, 15.0)
MAX_CLOCK_SKEW = timedelta(minutes=5)


class EidasTrustedListVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class _VerifiedXml:
    root: etree._Element
    sha256: str
    signer_certificate_sha256: str


@dataclass(frozen=True)
class _ServiceState:
    service_type: str
    service_status: str
    starts_at: datetime
    ends_at: datetime | None
    certificate_sha256: tuple[str, ...]
    service_name: str | None


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _aware(value: str, *, label: str) -> datetime:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EidasTrustedListVerificationError(f"invalid {label}") from exc
    if parsed.tzinfo is None:
        raise EidasTrustedListVerificationError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _local_name(node: etree._Element) -> str:
    try:
        return etree.QName(node).localname
    except ValueError as exc:
        raise EidasTrustedListVerificationError("trusted-list XML contains an invalid element name") from exc


def _children(node: etree._Element, local_name: str) -> list[etree._Element]:
    return [child for child in node if isinstance(child.tag, str) and _local_name(child) == local_name]


def _descendants(node: etree._Element, local_name: str) -> list[etree._Element]:
    return [item for item in node.iter() if isinstance(item.tag, str) and _local_name(item) == local_name]


def _text(node: etree._Element | None) -> str | None:
    if node is None:
        return None
    text = "".join(node.itertext()).strip()
    return text or None


def _first_descendant_text(node: etree._Element, local_name: str) -> str | None:
    matches = _descendants(node, local_name)
    return _text(matches[0]) if matches else None


def _parse_xml(value: bytes, *, label: str) -> etree._Element:
    if not isinstance(value, bytes) or not value or len(value) > MAX_TRUSTED_LIST_BYTES:
        raise EidasTrustedListVerificationError(f"invalid {label} size")
    upper_head = value[:4096].upper()
    if b"<!DOCTYPE" in upper_head or b"<!ENTITY" in upper_head:
        raise EidasTrustedListVerificationError(f"{label} DTD/entities are forbidden")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        huge_tree=False,
        remove_comments=False,
    )
    try:
        root = etree.fromstring(value, parser=parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise EidasTrustedListVerificationError(f"invalid {label} XML") from exc
    if _local_name(root) != "TrustServiceStatusList":
        raise EidasTrustedListVerificationError(f"{label} root is not TrustServiceStatusList")
    return root


def _pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def _certificate_from_der_b64(value: str, *, label: str) -> x509.Certificate:
    compact = "".join(str(value or "").split())
    try:
        der = base64.b64decode(compact, validate=True)
        return x509.load_der_x509_certificate(der)
    except (ValueError, TypeError) as exc:
        raise EidasTrustedListVerificationError(f"invalid {label} X509 certificate") from exc


def _certificates_in(node: etree._Element) -> list[x509.Certificate]:
    result: list[x509.Certificate] = []
    for cert_node in _descendants(node, "X509Certificate"):
        raw = _text(cert_node)
        if raw:
            result.append(_certificate_from_der_b64(raw, label="trusted-list"))
    return result


def _signed_root(result: object) -> etree._Element | None:
    candidates = result if isinstance(result, list) else [result]
    for candidate in candidates:
        signed_xml = getattr(candidate, "signed_xml", None)
        if signed_xml is not None and isinstance(getattr(signed_xml, "tag", None), str):
            if _local_name(signed_xml) == "TrustServiceStatusList":
                return signed_xml
    return None


def _verify_xmldsig(
    xml_bytes: bytes,
    *,
    signer_certificates: Sequence[x509.Certificate],
    label: str,
    verification_time: datetime,
) -> _VerifiedXml:
    root = _parse_xml(xml_bytes, label=label)
    if not signer_certificates:
        raise EidasTrustedListVerificationError(f"no trusted {label} signing certificate")
    errors: list[str] = []
    for cert in signer_certificates:
        try:
            config = SignatureConfiguration(
                location="./",
                expect_references=True,
                verification_time=verification_time,
            )
            result = XMLVerifier().verify(root, x509_cert=cert, expect_config=config)
            signed = _signed_root(result)
            if signed is None:
                raise EidasTrustedListVerificationError(f"{label} signature did not cover the trusted-list root")
            return _VerifiedXml(
                root=signed,
                sha256=_sha256(xml_bytes),
                signer_certificate_sha256=cert.fingerprint(hashes.SHA256()).hex(),
            )
        except Exception as exc:
            errors.append(type(exc).__name__)
    raise EidasTrustedListVerificationError(
        f"{label} XMLDSig verification failed for all pinned signers: {','.join(sorted(set(errors)))}"
    )


def _sequence(root: etree._Element, *, label: str) -> str:
    value = _first_descendant_text(root, "TSLSequenceNumber")
    if value is None:
        raise EidasTrustedListVerificationError(f"{label} sequence number is missing")
    return value


def _territory(root: etree._Element, *, label: str) -> str:
    value = (_first_descendant_text(root, "SchemeTerritory") or "").strip().upper()
    if len(value) != 2 or not value.isalpha():
        raise EidasTrustedListVerificationError(f"{label} scheme territory is invalid")
    return value


def _list_dates(root: etree._Element, *, label: str) -> tuple[datetime, datetime]:
    issue_text = _first_descendant_text(root, "ListIssueDateTime")
    next_update_nodes = _descendants(root, "NextUpdate")
    next_text = _first_descendant_text(next_update_nodes[0], "dateTime") if next_update_nodes else None
    if issue_text is None or next_text is None:
        raise EidasTrustedListVerificationError(f"{label} issue/next-update metadata is missing")
    issue = _aware(issue_text, label=f"{label} issue date")
    next_update = _aware(next_text, label=f"{label} next update")
    if next_update <= issue:
        raise EidasTrustedListVerificationError(f"{label} update interval is invalid")
    return issue, next_update


def _require_current(root: etree._Element, *, label: str, now: datetime) -> None:
    issue, next_update = _list_dates(root, label=label)
    if issue > now + MAX_CLOCK_SKEW:
        raise EidasTrustedListVerificationError(f"{label} issue date is in the future")
    if next_update <= now - MAX_CLOCK_SKEW:
        raise EidasTrustedListVerificationError(f"{label} is stale")


def _https_uri(value: str, *, label: str) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise EidasTrustedListVerificationError(f"{label} must be a credential-free HTTPS URL")
    return text


def _member_state_pointer(
    lotl_root: etree._Element,
    *,
    territory: str,
) -> tuple[str, list[x509.Certificate]]:
    matches: list[tuple[str, list[x509.Certificate]]] = []
    for pointer in _descendants(lotl_root, "OtherTSLPointer"):
        territories = {str(_text(item) or "").strip().upper() for item in _descendants(pointer, "SchemeTerritory")}
        if territory not in territories:
            continue
        location = _first_descendant_text(pointer, "TSLLocation")
        if location is None:
            continue
        certs = _certificates_in(pointer)
        if certs:
            matches.append((_https_uri(location, label="member-state TL location"), certs))
    unique_locations = {item[0] for item in matches}
    if len(unique_locations) != 1:
        raise EidasTrustedListVerificationError("signed LOTL does not resolve exactly one member-state TL location")
    location = next(iter(unique_locations))
    certs_by_fp: dict[str, x509.Certificate] = {}
    for candidate_location, certs in matches:
        if candidate_location != location:
            continue
        for cert in certs:
            certs_by_fp[cert.fingerprint(hashes.SHA256()).hex()] = cert
    if not certs_by_fp:
        raise EidasTrustedListVerificationError("signed LOTL pointer contains no member-state TL signing identity")
    return location, list(certs_by_fp.values())


def _direct_child(node: etree._Element, local_name: str) -> etree._Element | None:
    values = _children(node, local_name)
    return values[0] if values else None


def _service_state_from_entry(entry: etree._Element) -> tuple[str, str, datetime, tuple[str, ...], str | None]:
    service_type = _first_descendant_text(entry, "ServiceTypeIdentifier")
    service_status = _first_descendant_text(entry, "ServiceStatus")
    starts = _first_descendant_text(entry, "StatusStartingTime")
    if service_type is None or service_status is None or starts is None:
        raise EidasTrustedListVerificationError("trusted-list service state is incomplete")
    certificates = tuple(sorted({cert.fingerprint(hashes.SHA256()).hex() for cert in _certificates_in(entry)}))
    names = _descendants(entry, "ServiceName")
    service_name = _first_descendant_text(names[0], "Name") if names else None
    return service_type.strip(), service_status.strip(), _aware(starts, label="service status start"), certificates, service_name


def _states_for_service(service: etree._Element) -> list[_ServiceState]:
    raw: list[tuple[str, str, datetime, tuple[str, ...], str | None]] = []
    information = _direct_child(service, "ServiceInformation")
    if information is None:
        raise EidasTrustedListVerificationError("TSP service has no ServiceInformation")
    raw.append(_service_state_from_entry(information))
    history = _direct_child(service, "ServiceHistory")
    if history is not None:
        for item in _children(history, "ServiceHistoryInstance"):
            raw.append(_service_state_from_entry(item))
    raw.sort(key=lambda item: item[2])
    starts = [item[2] for item in raw]
    if len(starts) != len(set(starts)):
        raise EidasTrustedListVerificationError("service history contains ambiguous duplicate start times")
    states: list[_ServiceState] = []
    for index, item in enumerate(raw):
        end = raw[index + 1][2] if index + 1 < len(raw) else None
        states.append(
            _ServiceState(
                service_type=item[0],
                service_status=item[1],
                starts_at=item[2],
                ends_at=end,
                certificate_sha256=item[3],
                service_name=item[4],
            )
        )
    return states


def _qualified_service_at(
    tl_root: etree._Element,
    *,
    certificate: x509.Certificate,
    gen_time: datetime,
) -> _ServiceState:
    fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
    candidates: list[_ServiceState] = []
    for service in _descendants(tl_root, "TSPService"):
        states = _states_for_service(service)
        active = [
            state for state in states
            if state.starts_at <= gen_time and (state.ends_at is None or gen_time < state.ends_at)
        ]
        if len(active) > 1:
            raise EidasTrustedListVerificationError("trusted-list service history is ambiguous at token time")
        if not active:
            continue
        state = active[0]
        if state.service_type != EIDAS_QTST_SERVICE_TYPE:
            continue
        if state.service_status != EIDAS_GRANTED_STATUS:
            continue
        if fingerprint not in state.certificate_sha256:
            continue
        candidates.append(state)
    if len(candidates) != 1:
        raise EidasTrustedListVerificationError(
            "exact TSA certificate is not uniquely covered by a granted TSA/QTST service at token time"
        )
    return candidates[0]


class SignedEidasTrustedListVerifier:
    """Cryptographically derive eIDAS qualification from LOTL and a national TL.

    Trust starts only from pinned European Commission LOTL signing certificates
    supplied out-of-band by the operator. The national TL URL and its signing
    certificates are then accepted only if they occur inside that verified LOTL.
    No Dashboard/API boolean is used as a validation authority.
    """

    def __init__(
        self,
        *,
        territory: str,
        lotl_signing_certificates_pem: Sequence[bytes],
        session: requests.Session | None = None,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
        lotl_uri: str = EU_LOTL_URI,
    ) -> None:
        territory_value = str(territory or "").strip().upper()
        if len(territory_value) != 2 or not territory_value.isalpha():
            raise EidasTrustedListVerificationError("territory must be a two-letter code")
        if lotl_uri != EU_LOTL_URI:
            raise EidasTrustedListVerificationError("LOTL URI must be the canonical European Commission LOTL")
        certificates: list[x509.Certificate] = []
        for blob in lotl_signing_certificates_pem:
            if not isinstance(blob, bytes) or not blob.strip():
                raise EidasTrustedListVerificationError("LOTL signing certificate PEM is required")
            try:
                certificates.extend(x509.load_pem_x509_certificates(blob))
            except ValueError as exc:
                raise EidasTrustedListVerificationError("LOTL signing certificate PEM is invalid") from exc
        if not certificates:
            raise EidasTrustedListVerificationError("at least one pinned LOTL signing certificate is required")
        self.territory = territory_value
        self.lotl_signers = certificates
        self.session = session or requests.Session()
        self.timeout = timeout
        self.lotl_uri = lotl_uri

    def _get(self, uri: str, *, label: str) -> bytes:
        _https_uri(uri, label=label)
        try:
            response = self.session.get(
                uri,
                headers={"Accept": "application/xml,text/xml;q=0.9"},
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise EidasTrustedListVerificationError(f"{label} download failed") from exc
        if response.is_redirect:
            raise EidasTrustedListVerificationError(f"{label} redirect rejected")
        if response.status_code != 200:
            raise EidasTrustedListVerificationError(f"{label} HTTP status is not 200")
        content = bytes(response.content)
        if not content or len(content) > MAX_TRUSTED_LIST_BYTES:
            raise EidasTrustedListVerificationError(f"{label} response size is invalid")
        return content

    def verify(
        self,
        *,
        certificate: x509.Certificate,
        gen_time: datetime,
    ) -> EidasQualifiedTimestampEvidence:
        if not isinstance(certificate, x509.Certificate):
            raise EidasTrustedListVerificationError("TSA certificate is required")
        instant = gen_time.astimezone(timezone.utc) if gen_time.tzinfo else gen_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if instant > now + MAX_CLOCK_SKEW:
            raise EidasTrustedListVerificationError("timestamp genTime is implausibly in the future")

        lotl_bytes = self._get(self.lotl_uri, label="EU LOTL")
        lotl = _verify_xmldsig(
            lotl_bytes,
            signer_certificates=self.lotl_signers,
            label="EU LOTL",
            verification_time=now,
        )
        _require_current(lotl.root, label="EU LOTL", now=now)
        tl_uri, tl_signers = _member_state_pointer(lotl.root, territory=self.territory)

        tl_bytes = self._get(tl_uri, label=f"{self.territory} trusted list")
        tl = _verify_xmldsig(
            tl_bytes,
            signer_certificates=tl_signers,
            label=f"{self.territory} trusted list",
            verification_time=now,
        )
        _require_current(tl.root, label=f"{self.territory} trusted list", now=now)
        if _territory(tl.root, label=f"{self.territory} trusted list") != self.territory:
            raise EidasTrustedListVerificationError("member-state trusted-list territory does not match LOTL pointer")

        state = _qualified_service_at(tl.root, certificate=certificate, gen_time=instant)
        return EidasQualifiedTimestampEvidence(
            territory=self.territory,
            service_type=state.service_type,
            service_status=state.service_status,
            service_certificate_sha256=certificate.fingerprint(hashes.SHA256()).hex(),
            service_valid_from=state.starts_at.isoformat(),
            service_valid_until=None if state.ends_at is None else state.ends_at.isoformat(),
            service_name=state.service_name,
            lotl_uri=self.lotl_uri,
            lotl_sha256=lotl.sha256,
            lotl_sequence=_sequence(lotl.root, label="EU LOTL"),
            lotl_signer_certificate_sha256=lotl.signer_certificate_sha256,
            national_tl_uri=tl_uri,
            national_tl_sha256=tl.sha256,
            national_tl_sequence=_sequence(tl.root, label=f"{self.territory} trusted list"),
            national_tl_signer_certificate_sha256=tl.signer_certificate_sha256,
            verification_method=EIDAS_CHAIN_VERIFICATION_METHOD,
            verified_at=now.isoformat(),
        )
