import base64
import json
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from licensing.generator import build_license_key
from licensing.validator import validate_license_key_for_machine


def _decode_payload(license_key: str) -> dict:
    payload_base64url = license_key.split(".")[1]
    payload_json = base64.urlsafe_b64decode(
        payload_base64url + "=" * (-len(payload_base64url) % 4)
    ).decode("utf-8")
    return json.loads(payload_json)


class LicenseGeneratorTests(TestCase):
    def test_same_machine_id_generates_the_same_key(self):
        machine_id = "1cd90f24bf0dacb7b03fcba11781052c36b622269690a445771413fd592278b3"

        license_key_1 = build_license_key(machine_id=machine_id)
        license_key_2 = build_license_key(machine_id=machine_id)

        self.assertEqual(license_key_1, license_key_2)

        payload = _decode_payload(license_key_1)
        self.assertEqual(
            payload,
            {
                "app": "GestaoOficina",
                "machine_id": machine_id,
            },
        )

    def test_web_generated_license_is_valid_for_the_machine(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="license-admin",
            email="license-admin@example.com",
            password="password123",
        )
        self.client.force_login(user)

        machine_id = "1cd90f24bf0dacb7b03fcba11781052c36b622269690a445771413fd592278b3"
        response_1 = self.client.post(
            reverse("core:licenca_gestao_oficina"),
            {
                "machine_id": machine_id,
            },
        )
        response_2 = self.client.post(
            reverse("core:licenca_gestao_oficina"),
            {
                "machine_id": machine_id,
            },
        )

        self.assertEqual(response_1.status_code, 200)
        self.assertEqual(response_2.status_code, 200)

        key_1 = re.search(r"GOF1\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", response_1.content.decode("utf-8"))
        key_2 = re.search(r"GOF1\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", response_2.content.decode("utf-8"))

        self.assertIsNotNone(key_1)
        self.assertIsNotNone(key_2)
        self.assertEqual(key_1.group(0), key_2.group(0))

        payload = validate_license_key_for_machine(key_1.group(0), machine_id=machine_id)
        self.assertEqual(payload["app"], "GestaoOficina")
        self.assertEqual(payload["machine_id"], machine_id)
        self.assertEqual(sorted(payload.keys()), ["app", "machine_id"])

    def test_machine_id_must_match_exactly(self):
        machine_id = "1cd90f24bf0dacb7b03fcba11781052c36b622269690a445771413fd592278b3"

        license_key = build_license_key(machine_id=machine_id)

        with self.assertRaises(ValueError):
            validate_license_key_for_machine(
                license_key,
                machine_id="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            )
