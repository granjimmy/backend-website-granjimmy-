"""Cria os grupos 'Médicos' e 'Editores' com as permissões corretas.

Idempotente: pode rodar quantas vezes precisar.
    python manage.py criar_grupos
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from blog.models import Author, Category, Post, Tag
from newsletter.models import Campaign, Subscriber


class Command(BaseCommand):
    help = "Cria/atualiza os grupos de acesso ao painel."

    def handle(self, *args, **options):
        # Médico: cria e edita as próprias publicações (o admin restringe
        # ao autor e bloqueia publicar direto). Leitura em apoio.
        medicos, _ = Group.objects.get_or_create(name="Médicos")
        medicos.permissions.set(
            self._perms(
                (Post, ["add", "change", "view", "delete"]),
                (Author, ["view", "change"]),
                (Category, ["view"]),
                (Tag, ["view", "add"]),
            )
        )

        # Editor: controle editorial completo, inclusive publicar e newsletter.
        editores, _ = Group.objects.get_or_create(name="Editores")
        editores.permissions.set(
            self._perms(
                (Post, ["add", "change", "view", "delete"]),
                (Author, ["add", "change", "view", "delete"]),
                (Category, ["add", "change", "view", "delete"]),
                (Tag, ["add", "change", "view", "delete"]),
                (Subscriber, ["view", "change", "delete"]),
                (Campaign, ["view"]),
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Grupos prontos: Médicos ({medicos.permissions.count()} permissões), "
                f"Editores ({editores.permissions.count()} permissões)."
            )
        )
        self.stdout.write(
            "Lembre-se: a conta do médico precisa de is_staff=True para entrar no painel, "
            "e de um perfil de Autor vinculado para assinar publicações."
        )

    def _perms(self, *specs):
        out = []
        for model, actions in specs:
            ct = ContentType.objects.get_for_model(model)
            for action in actions:
                codename = f"{action}_{model._meta.model_name}"
                try:
                    out.append(Permission.objects.get(content_type=ct, codename=codename))
                except Permission.DoesNotExist:
                    self.stderr.write(f"permissão ausente: {codename}")
        return out
