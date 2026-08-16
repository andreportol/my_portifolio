from base64 import urlsafe_b64decode
from datetime import datetime, timezone
import json

from django.test import TestCase

from licensing.validator import generate_license_key, verify_license_key


class LicenseGeneratorTests(TestCase):
    def test_customer_name_is_normalized_without_accents(self):
        machine_id = "1cd90f24bf0dacb7b03fcba11781052c36b622269690a445771413fd592278b3"
        issued_at = datetime(2026, 8, 15, 23, 0, 5, 750612, tzinfo=timezone.utc)

        license_without_accent = generate_license_key(
            machine_id=machine_id,
            customer="Andre Porto",
            issued_at=issued_at,
        )
        license_with_accent = generate_license_key(
            machine_id=machine_id,
            customer="André Porto",
            issued_at=issued_at,
        )

        self.assertEqual(license_without_accent, license_with_accent)

        payload_base64url = license_without_accent.split(".")[1]
        payload_json = urlsafe_b64decode(payload_base64url + "=" * (-len(payload_base64url) % 4)).decode("utf-8")
        payload = json.loads(payload_json)
        self.assertEqual(payload["customer"], "Andre Porto")

    def test_generated_license_is_valid_for_the_machine(self):
        machine_id = "1cd90f24bf0dacb7b03fcba11781052c36b622269690a445771413fd592278b3"
        issued_at = datetime(2026, 8, 15, 23, 0, 5, 750612, tzinfo=timezone.utc)

        license_key = generate_license_key(
            machine_id=machine_id,
            customer="André Porto",
            issued_at=issued_at,
        )

        payload = verify_license_key(license_key, machine_id=machine_id)
        self.assertEqual(payload["machine_id"], machine_id)
        self.assertEqual(payload["customer"], "Andre Porto")
