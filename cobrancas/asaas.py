import requests
from django.conf import settings


class AsaasError(RuntimeError):
    def __init__(self, message, *, status_code=None, errors=None):
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors

    @property
    def emissao_rejeitada(self):
        # Apenas uma resposta explícita do Asaas confirma a rejeição.
        # Timeout, erro de proxy e falha 5xx continuam exigindo reconciliação.
        return self.status_code in {400, 401, 403} and isinstance(self.errors, list) and bool(self.errors)


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
            raise AsaasError(
                f"Asaas HTTP {response.status_code}: {detail}",
                status_code=response.status_code,
                errors=detail.get("errors") if isinstance(detail, dict) else None,
            )
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

    def obter_cobranca(self, payment_id):
        return self._request("GET", f"/payments/{payment_id}")

    def excluir_cobranca(self, payment_id):
        resultado = self._request("DELETE", f"/payments/{payment_id}")
        if resultado.get('deleted') is not True:
            raise AsaasError('O Asaas não confirmou a exclusão da cobrança antiga.')
        return resultado

    def buscar_cobranca(self, customer_id, external_reference):
        resultado = self._request("GET", "/payments", params={
            "customer": customer_id, "externalReference": external_reference,
            "billingType": "PIX", "limit": 2,
        })
        cobrancas = resultado.get("data", [])
        if len(cobrancas) > 1 or resultado.get("hasMore"):
            raise AsaasError("Mais de uma cobrança encontrada para esta mensalidade. Reconcilie no Asaas.")
        return cobrancas[0] if cobrancas else None

    def corrigir_cobranca_pix(self, payment_id, value, due_date):
        from decimal import Decimal
        cobranca = self._request("GET", f"/payments/{payment_id}")
        if (cobranca.get("customer") != settings.ASAAS_CUSTOMER_ID
                or cobranca.get("billingType") != "PIX"
                or cobranca.get("deleted")
                or cobranca.get("status") not in {"PENDING", "OVERDUE"}):
            raise AsaasError("Cobrança indisponível para correção.")
        referencia = f"marmitaria-adriana-{due_date.isoformat()}"
        existente = self.buscar_cobranca(settings.ASAAS_CUSTOMER_ID, referencia)
        if existente and existente.get("id") != payment_id:
            raise AsaasError("Já existe outra cobrança para o vencimento informado.")
        resultado = self._request("PUT", f"/payments/{payment_id}", json={
            "billingType": "PIX", "value": float(value),
            "dueDate": due_date.isoformat(), "externalReference": referencia,
        })
        if (resultado.get("id") != payment_id
                or Decimal(str(resultado.get("value", 0))) != value
                or resultado.get("dueDate") != due_date.isoformat()
                or resultado.get("externalReference") != referencia):
            raise AsaasError("Resposta divergente na correção da cobrança.")
        return resultado
