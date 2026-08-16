from licensing.generator import build_license_key


def gerar_codigo_licenca_gestao_oficina(machine_id: str) -> str:
    return build_license_key(machine_id=machine_id)


def gerar_codigo_licenca_gestao_salao_beleza(machine_id: str) -> str:
    return build_license_key(machine_id=machine_id)
