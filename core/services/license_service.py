from licensing.generator import generate_license_key


def gerar_codigo_licenca_gestao_oficina(machine_id: str, customer: str) -> str:
    return generate_license_key(machine_id=machine_id, customer=customer)


def gerar_codigo_licenca_gestao_salao_beleza(machine_id: str, customer: str) -> str:
    return generate_license_key(machine_id=machine_id, customer=customer)
