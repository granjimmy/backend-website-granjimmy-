from django.contrib import admin

from .models import Campaign, Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "status", "confirmed_at", "created")
    list_filter = ("status", "created")
    search_fields = ("email", "name")
    readonly_fields = ("token", "consent_ip", "confirmed_at", "unsubscribed_at", "created")
    date_hierarchy = "created"


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("subject", "post", "recipients", "sent_at", "created")
    list_filter = ("sent_at",)
    search_fields = ("subject",)
    readonly_fields = ("recipients", "sent_at", "created")
