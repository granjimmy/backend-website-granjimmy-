"""Cadastro de pessoas que recebem aviso de novas publicações do blog."""

import secrets

from django.db import models


class Subscriber(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Aguardando confirmação"
        CONFIRMED = "confirmed", "Confirmado"
        UNSUBSCRIBED = "unsubscribed", "Descadastrado"

    email = models.EmailField("e-mail", unique=True)
    name = models.CharField("nome", max_length=160, blank=True)
    status = models.CharField(
        "situação",
        max_length=14,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    # Double opt-in: exigido pela LGPD para comprovar o consentimento.
    token = models.CharField("token", max_length=64, unique=True, editable=False)
    consent_ip = models.GenericIPAddressField("IP do consentimento", null=True, blank=True)
    confirmed_at = models.DateTimeField("confirmado em", null=True, blank=True)
    unsubscribed_at = models.DateTimeField("descadastrado em", null=True, blank=True)
    created = models.DateTimeField("cadastrado em", auto_now_add=True)

    class Meta:
        verbose_name = "inscrito"
        verbose_name_plural = "inscritos"
        ordering = ["-created"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class Campaign(models.Model):
    """Registro de um disparo de newsletter referente a uma publicação.

    Serve de trilha de auditoria: o que foi enviado, quando e para quantos.
    """

    post = models.ForeignKey(
        "blog.Post",
        on_delete=models.CASCADE,
        related_name="campaigns",
        verbose_name="publicação",
    )
    subject = models.CharField("assunto", max_length=250)
    sent_at = models.DateTimeField("enviada em", null=True, blank=True)
    recipients = models.PositiveIntegerField("destinatários", default=0)
    created = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "campanha"
        verbose_name_plural = "campanhas"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.subject} ({self.recipients} destinatários)"
