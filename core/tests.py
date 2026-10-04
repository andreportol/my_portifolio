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
    def test_license_dashboard_offers_project_catalog_and_generator(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="license-dashboard",
            email="license-dashboard@example.com",
            password="password123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:licencas"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visualizar dados dos projetos")
        self.assertContains(response, "Gerar licença dos softwares")
        self.assertContains(response, reverse("core:licencas_projetos"))
        self.assertContains(response, reverse("core:licenca_softwares"))

    def test_license_project_catalog_excludes_licensed_software(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="license-projects",
            email="license-projects@example.com",
            password="password123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:licencas_projetos"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Gestão Oficina")
        self.assertNotContains(response, "Gestão Salão Beleza")
        self.assertNotContains(response, reverse("core:licenca_gestao_salao_beleza"))
        self.assertContains(response, "marmitaria_adriana")

        licensing = self.client.get(reverse("core:licenca_softwares"))
        self.assertEqual(licensing.status_code, 200)
        self.assertContains(licensing, reverse("core:licenca_gestao_salao_beleza"))

    def test_project_details_require_login(self):
        url = reverse('core:licenca_projeto_detalhe', kwargs={'slug': 'marmitaria_adriana'})
        response = self.client.get(url)
        self.assertRedirects(response, reverse('core:entrar') + '?next=' + url)

    def test_project_catalog_links_to_marmitaria_details(self):
        user = get_user_model().objects.create_user(username='project-details')
        self.client.force_login(user)
        url = reverse('core:licenca_projeto_detalhe', kwargs={'slug': 'marmitaria_adriana'})
        catalog = self.client.get(reverse('core:licencas_projetos'))
        self.assertContains(catalog, url)
        response = self.client.get(url)
        self.assertContains(response, 'marmitaria_adriana')
        self.assertContains(response, 'Em implementação')
        self.assertNotContains(response, 'Gerar licença')
        unknown = reverse('core:licenca_projeto_detalhe', kwargs={'slug': 'inexistente'})
        self.assertEqual(self.client.get(unknown).status_code, 404)

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
            reverse("core:licenca_softwares"),
            {
                "machine_id": machine_id,
            },
        )
        response_2 = self.client.post(
            reverse("core:licenca_softwares"),
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
