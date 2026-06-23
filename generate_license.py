import argparse

from licensing.generator import generate_license_key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gerador offline de licenças para o sistema Gestão Oficina."
    )
    parser.add_argument("--machine-id", required=True, help="ID da máquina informado pelo cliente.")
    parser.add_argument("--customer", required=True, help="Nome do cliente/licenciado.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    license_key = generate_license_key(
        machine_id=args.machine_id.strip(),
        customer=args.customer.strip(),
    )
    print(license_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
