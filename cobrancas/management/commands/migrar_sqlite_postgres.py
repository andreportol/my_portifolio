import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.core.management.color import no_style
from django.db import connections, transaction


EXCLUDES = (
    "contenttypes",
    "auth.permission",
    "sessions",
    "admin.logentry",
)


def _portable_models():
    excluded_labels = {"contenttypes.contenttype", "auth.permission", "sessions.session", "admin.logentry"}
    for model in apps.get_models():
        opts = model._meta
        if opts.proxy or not opts.managed or opts.auto_created:
            continue
        if opts.label_lower in excluded_labels:
            continue
        yield model


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Command(BaseCommand):
    help = "Migra, uma única vez e com validação, o db.sqlite3 legado para o PostgreSQL configurado em DATABASE_URL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=str(Path(settings.BASE_DIR) / "db.sqlite3"),
            help="Caminho do SQLite legado. O padrão é BASE_DIR/db.sqlite3.",
        )

    def handle(self, *args, **options):
        source = Path(options["source"]).resolve()
        if connections["default"].vendor != "postgresql":
            raise CommandError("O banco default não é PostgreSQL. Configure DATABASE_URL antes de executar.")
        if not source.exists() or not source.is_file() or source.stat().st_size == 0:
            raise CommandError(f"SQLite legado não encontrado ou vazio: {source}")

        self.stdout.write(f"SQLite legado: {source}")
        self.stdout.write(f"Tamanho: {source.stat().st_size} bytes")
        self.stdout.write(f"SHA256: {_sha256(source)}")

        # Cria somente o schema e as tabelas de sistema do PostgreSQL.
        call_command("migrate", database="default", interactive=False, verbosity=1)

        # Após migrate, o destino pode conter contenttypes/permissões, mas não deve
        # conter usuários nem dados de negócio. Assim evitamos sobrepor dados.
        ocupados = []
        for model in _portable_models():
            try:
                quantidade = model.objects.using("default").count()
            except Exception as exc:
                raise CommandError(f"Falha ao verificar {model._meta.label}: {exc}") from exc
            if quantidade:
                ocupados.append(f"{model._meta.label}={quantidade}")
        if ocupados:
            raise CommandError(
                "PostgreSQL já contém dados migráveis; migração abortada para evitar sobrescrita: "
                + ", ".join(ocupados)
            )

        fixture_file = tempfile.NamedTemporaryFile(prefix="sqlite-legacy-", suffix=".json", delete=False)
        fixture_path = Path(fixture_file.name)
        fixture_file.close()
        try:
            # Executa dumpdata em outro processo sem DATABASE_URL; assim o mesmo
            # settings.py abre o db.sqlite3 legado como banco default.
            env = os.environ.copy()
            env.pop("DATABASE_URL", None)
            env["COBRANCA_AUTOMATICA_ENABLED"] = "False"
            command = [
                sys.executable,
                str(Path(settings.BASE_DIR) / "manage.py"),
                "dumpdata",
                "--natural-foreign",
                "--indent=2",
                f"--output={fixture_path}",
            ]
            for excluded in EXCLUDES:
                command.extend(["--exclude", excluded])

            result = subprocess.run(
                command,
                cwd=settings.BASE_DIR,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode != 0:
                raise CommandError(
                    "Falha ao exportar SQLite legado: " + (result.stderr.strip() or result.stdout.strip())
                )

            try:
                payload = json.loads(fixture_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise CommandError(f"Fixture gerada é inválida: {exc}") from exc
            if not isinstance(payload, list):
                raise CommandError("Fixture gerada não é uma lista JSON.")

            esperado = Counter(item.get("model") for item in payload if isinstance(item, dict) and item.get("model"))
            self.stdout.write(f"Objetos exportados do SQLite: {sum(esperado.values())}")
            for label, count in sorted(esperado.items()):
                self.stdout.write(f"  {label}: {count}")

            with transaction.atomic(using="default"):
                call_command("loaddata", str(fixture_path), database="default", verbosity=1)

                divergencias = []
                for label, expected_count in esperado.items():
                    try:
                        model = apps.get_model(label)
                    except LookupError:
                        divergencias.append(f"{label}: modelo não encontrado")
                        continue
                    actual = model.objects.using("default").count()
                    if actual != expected_count:
                        divergencias.append(f"{label}: esperado={expected_count}, postgres={actual}")
                if divergencias:
                    raise CommandError(
                        "Validação falhou; a transação será revertida: " + "; ".join(divergencias)
                    )

                # Ajusta sequences do PostgreSQL para os PKs preservados do SQLite.
                models = list(_portable_models())
                sql_list = connections["default"].ops.sequence_reset_sql(no_style(), models)
                with connections["default"].cursor() as cursor:
                    for sql in sql_list:
                        cursor.execute(sql)

            self.stdout.write(self.style.SUCCESS("Migração SQLite -> PostgreSQL concluída e validada."))
        finally:
            try:
                fixture_path.unlink(missing_ok=True)
            except OSError:
                pass
