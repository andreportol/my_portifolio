import requests
from django.conf import settings


class AsaasError(RuntimeError):
    pass


class AsaasClient:
    def __init__(self):
        self.base_url = settings.ASAAS_API_URL.rstrip("/")
        self.api_key = settings.ASAAS_API_KEY
        self.timeout = settings.ASAAS_REQUEST_TIMEOUT
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "User-Agent": settings.ASAAS_USER_AGENT,
            "access_token": self.api_key,
        }

    def _request(self, method, path, **kwargs):
        if not self.api_key:
            raise AsaasError("ASAAS_API_KEY não configurada.")
        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=self.headers,
            timeout=self.timeout,
            **kwargs,
        )
        if not response.ok:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise AsaasError(f"Asaas HTTP {response.status_code}: {detail}")
        return response.json()

    def criar_cobranca_pix(self, customer_id, value, due_date, description, external_reference):
        return self._request(
            "POST",
            "/payments",
            json={
                "customer": customer_id,
                "billingType": "PIX",
                "value": float(value),
                "dueDate": due_date.isoformat(),
                "description": description,
                "externalReference": external_reference,
            },
        )

    def obter_pix(self, payment_id):
        return self._request("GET", f"/payments/{payment_id}/pixQrCode")

    def buscar_cobranca(self, customer_id, external_reference):
        resultado = self._request("GET", "/payments", params={
            "customer": customer_id, "externalReference": external_reference,
            "billingType": "PIX", "limit": 2,
        })
        cobrancas = resultado.get("data", [])
        if len(cobrancas) > 1 or resultado.get("hasMore"):
            raise AsaasError("Mais de uma cobrança encontrada para esta mensalidade. Reconcilie no Asaas.")
        return cobrancas[0] if cobrancas else None
