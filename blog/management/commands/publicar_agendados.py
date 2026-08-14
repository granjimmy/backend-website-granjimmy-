"""Publica posts agendados e notifica os inscritos da newsletter.

Rodar de minuto em minuto (cron ou systemd timer):
    python manage.py publicar_agendados

O comando é idempotente: newsletter_sent_at impede envio duplicado.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from blog.models import Post
from newsletter.models import Campaign, Subscriber


class Command(BaseCommand):
    help = "Publica posts agendados cuja data chegou e dispara a newsletter."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria feito, sem gravar nem enviar.",
        )
        parser.add_argument(
            "--no-email",
            action="store_true",
            help="Publica os posts mas não envia a newsletter.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        now = timezone.now()

        due = Post.objects.filter(status=Post.Status.SCHEDULED, published_at__lte=now)
        count = due.count()
        if count:
            self.stdout.write(f"{count} publicação(ões) agendada(s) com data atingida.")
            for post in due:
                self.stdout.write(f"  - {post.title} ({post.published_at:%d/%m/%Y %H:%M})")
            if not dry:
                due.update(status=Post.Status.PUBLISHED)
        else:
            self.stdout.write("Nenhuma publicação agendada para agora.")

        if options["no_email"]:
            self.stdout.write("Envio de newsletter pulado (--no-email).")
            return

        pending = Post.objects.published().filter(newsletter_sent_at__isnull=True)
        if not pending.exists():
            self.stdout.write("Nenhuma newsletter pendente.")
            return

        recipients = list(
            Subscriber.objects.filter(status=Subscriber.Status.CONFIRMED).values_list(
                "email", "token"
            )
        )
        if not recipients:
            self.stdout.write(self.style.WARNING("Nenhum inscrito confirmado. Nada a enviar."))
            return

        for post in pending.select_related("author", "category"):
            subject = f"Novo artigo: {post.title}"
            self.stdout.write(f"Newsletter '{subject}' -> {len(recipients)} destinatário(s)")
            if dry:
                continue

            sent = self._send(post, subject, recipients)
            post.newsletter_sent_at = timezone.now()
            post.save(update_fields=["newsletter_sent_at"])
            Campaign.objects.create(
                post=post, subject=subject, sent_at=timezone.now(), recipients=sent
            )
            self.stdout.write(self.style.SUCCESS(f"  enviada para {sent}."))

    def _send(self, post, subject, recipients):
        site = getattr(settings, "SITE_URL", "https://granjimmy.com.br")
        connection = get_connection()
        sent = 0
        for email, token in recipients:
            ctx = {
                "post": post,
                "site_url": site,
                "post_url": f"{site}/blog/{post.slug}",
                "unsubscribe_url": f"{site}/newsletter/descadastro/{token}",
            }
            text = render_to_string("newsletter/post_notification.txt", ctx)
            html = render_to_string("newsletter/post_notification.html", ctx)
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
                connection=connection,
            )
            msg.attach_alternative(html, "text/html")
            # Um destinatário com e-mail inválido não pode abortar a campanha.
            try:
                msg.send()
                sent += 1
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"  falha para {email}: {exc}")
        return sent
