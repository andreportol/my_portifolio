from .validator import generate_license_key as _generate_license_key


def build_license_key(machine_id: str) -> str:
    return _generate_license_key(machine_id=machine_id)


generate_license_key = build_license_key
