"""Inscrição na newsletter com double opt-in (LGPD)."""

from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .models import Subscriber


class SubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=160, required=False, allow_blank=True)


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def subscribe(request):
    serializer = SubscribeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"].lower()

    sub, created = Subscriber.objects.get_or_create(
        email=email,
        defaults={
            "name": serializer.validated_data.get("name", ""),
            "consent_ip": client_ip(request),
        },
    )
    if not created and sub.status == Subscriber.Status.UNSUBSCRIBED:
        # Reinscrição: volta para pendente e exige nova confirmação.
        sub.status = Subscriber.Status.PENDING
        sub.unsubscribed_at = None
        sub.consent_ip = client_ip(request)
        sub.save(update_fields=["status", "unsubscribed_at", "consent_ip"])

    # Resposta idêntica para e-mail novo ou já cadastrado: não revela
    # quem está na base (enumeração de e-mails).
    return Response(
        {"detail": "Confirme sua inscrição no link enviado para o seu e-mail."},
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def confirm(request, token):
    try:
        sub = Subscriber.objects.get(token=token)
    except Subscriber.DoesNotExist:
        return Response({"detail": "Token inválido."}, status=status.HTTP_404_NOT_FOUND)

    if sub.status != Subscriber.Status.CONFIRMED:
        sub.status = Subscriber.Status.CONFIRMED
        sub.confirmed_at = timezone.now()
        sub.save(update_fields=["status", "confirmed_at"])
    return Response({"detail": "Inscrição confirmada."})


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def unsubscribe(request, token):
    try:
        sub = Subscriber.objects.get(token=token)
    except Subscriber.DoesNotExist:
        return Response({"detail": "Token inválido."}, status=status.HTTP_404_NOT_FOUND)

    sub.status = Subscriber.Status.UNSUBSCRIBED
    sub.unsubscribed_at = timezone.now()
    sub.save(update_fields=["status", "unsubscribed_at"])
    return Response({"detail": "Você não receberá mais nossos e-mails."})
