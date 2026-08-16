import base64
import hashlib
import hmac
import json

from . import APP_NAME, LICENSE_SECRET, TOKEN_PREFIX


def _normalize_machine_id(machine_id: str) -> str:
    value = (machine_id or "").strip().replace(" ", "").lower()
    if not value:
        raise ValueError("machine_id nao pode ficar vazio.")
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("ID da máquina inválido. Use um hash SHA-256 com 64 caracteres hexadecimais.")
    return value


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _canonical_payload(machine_id: str) -> str:
    payload = {
        "app": APP_NAME,
        "machine_id": _normalize_machine_id(machine_id),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sign(payload_base64url: str) -> str:
    digest = hmac.new(
        LICENSE_SECRET.encode("utf-8"),
        payload_base64url.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def generate_license_key(
    machine_id: str,
) -> str:
    payload_json = _canonical_payload(machine_id=machine_id)
    payload_base64url = _b64url_encode(payload_json.encode("utf-8"))
    signature_base64url = _sign(payload_base64url)
    return f"{TOKEN_PREFIX}.{payload_base64url}.{signature_base64url}"


def verify_license_key(license_key: str, machine_id: str) -> dict:
    parts = (license_key or "").strip().split(".")
    if len(parts) != 3:
        raise ValueError("Chave de licença inválida.")

    prefix, payload_base64url, signature_base64url = parts
    if prefix != TOKEN_PREFIX:
        raise ValueError("Prefixo de licença inválido.")

    expected_signature = _sign(payload_base64url)
    if not hmac.compare_digest(signature_base64url, expected_signature):
        raise ValueError("Assinatura da licença inválida.")

    payload_json = _b64url_decode(payload_base64url).decode("utf-8")
    payload = json.loads(payload_json)

    if payload.get("app") != APP_NAME:
        raise ValueError("Aplicação da licença inválida.")

    if payload.get("machine_id") != _normalize_machine_id(machine_id):
        raise ValueError("A licença não pertence a esta máquina.")

    return payload


validate_license_key_for_machine = verify_license_key
