"""Painel editorial usado pelos médicos.

Regra central de permissão: quem está no grupo "Médicos" enxerga e edita
apenas as próprias publicações e não pode publicar direto — envia para
revisão. Quem está em "Editores" (ou é staff pleno) vê tudo e publica.
"""

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import Author, Category, Post, Tag

EDITOR_GROUP = "Editores"
DOCTOR_GROUP = "Médicos"


def is_editor(user):
    return (
        user.is_superuser
        or user.groups.filter(name=EDITOR_GROUP).exists()
    )


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("photo_tag", "display_name", "credential", "specialty", "active")
    list_display_links = ("photo_tag", "display_name")
    list_filter = ("active", "specialty")
    search_fields = ("display_name", "credential", "specialty", "email")
    prepopulated_fields = {"slug": ("display_name",)}

    @admin.display(description="foto")
    def photo_tag(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="width:38px;height:38px;object-fit:cover;border-radius:50%">',
                obj.photo.url,
            )
        return "—"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if is_editor(request.user):
            return qs
        # Médico só enxerga o próprio perfil.
        return qs.filter(user=request.user)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "active")
    list_filter = ("active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "thumb",
        "title",
        "author",
        "category",
        "status_badge",
        "published_at",
        "newsletter_state",
    )
    list_display_links = ("thumb", "title")
    list_filter = ("status", "category", "author", "published_at")
    search_fields = ("title", "excerpt", "content")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)
    date_hierarchy = "published_at"
    actions = ("action_submit", "action_publish", "action_unpublish")

    fieldsets = (
        (
            "Publicação",
            {
                "fields": (
                    "title",
                    "slug",
                    "excerpt",
                    "cover_image",
                    "cover_alt",
                    "author",
                    "category",
                    "tags",
                )
            },
        ),
        ("Conteúdo", {"fields": ("content",)}),
        (
            "Agendamento",
            {
                "fields": ("status", "published_at"),
                "description": (
                    "Para agendar: escolha <b>Agendado</b> e informe uma data futura. "
                    "A publicação entra no ar sozinha na data marcada."
                ),
            },
        ),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    @admin.display(description="capa")
    def thumb(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="width:60px;height:40px;object-fit:cover;border-radius:4px">',
                obj.cover_image.url,
            )
        return "—"

    @admin.display(description="situação")
    def status_badge(self, obj):
        colors = {"draft": "#6b7280", "scheduled": "#b45309", "published": "#047857"}
        label = obj.get_status_display()
        if obj.status == Post.Status.SCHEDULED and obj.published_at:
            label = f"{label} · {obj.published_at:%d/%m/%Y %H:%M}"
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px">{}</span>',
            colors.get(obj.status, "#6b7280"),
            label,
        )

    @admin.display(description="newsletter")
    def newsletter_state(self, obj):
        if obj.newsletter_sent_at:
            return format_html(
                '<span title="{}">enviada</span>', f"{obj.newsletter_sent_at:%d/%m/%Y %H:%M}"
            )
        return "—"

    # --- restrição por autor -------------------------------------------------

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("author", "category")
        if is_editor(request.user):
            return qs
        return qs.filter(author__user=request.user)

    def get_readonly_fields(self, request, obj=None):
        # O médico não escolhe o autor: é sempre ele. Evita assinar em nome de outro.
        if not is_editor(request.user):
            return ("author",)
        return ()

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        # Médico não publica direto: só rascunho ou agendado (vai para revisão).
        if db_field.name == "status" and not is_editor(request.user):
            kwargs["choices"] = [
                (Post.Status.DRAFT, "Rascunho"),
                (Post.Status.SCHEDULED, "Agendado (envia para revisão)"),
            ]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not is_editor(request.user):
            profile = getattr(request.user, "author_profile", None)
            if profile is None:
                self.message_user(
                    request,
                    "Sua conta não está vinculada a um perfil de autor. "
                    "Peça ao administrador para criar o vínculo.",
                    level=messages.ERROR,
                )
                return
            obj.author = profile
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        if obj is not None and not is_editor(request.user):
            # Publicado vira somente-leitura para o médico: evita edição
            # silenciosa de conteúdo clínico que já está no ar.
            if obj.status == Post.Status.PUBLISHED:
                return False
            return obj.author.user_id == request.user.id
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and not is_editor(request.user):
            return obj.author.user_id == request.user.id and obj.status != Post.Status.PUBLISHED
        return super().has_delete_permission(request, obj)

    # --- ações em massa ------------------------------------------------------

    @admin.action(description="Enviar para revisão")
    def action_submit(self, request, queryset):
        n = queryset.update(status=Post.Status.SCHEDULED)
        self.message_user(request, f"{n} publicação(ões) enviada(s) para revisão.")

    @admin.action(description="Publicar agora")
    def action_publish(self, request, queryset):
        if not is_editor(request.user):
            self.message_user(
                request, "Apenas editores podem publicar.", level=messages.ERROR
            )
            return
        n = queryset.update(status=Post.Status.PUBLISHED, published_at=timezone.now())
        self.message_user(request, f"{n} publicação(ões) no ar.")

    @admin.action(description="Voltar para rascunho")
    def action_unpublish(self, request, queryset):
        if not is_editor(request.user):
            self.message_user(
                request, "Apenas editores podem despublicar.", level=messages.ERROR
            )
            return
        n = queryset.update(status=Post.Status.DRAFT)
        self.message_user(request, f"{n} publicação(ões) voltaram para rascunho.")


admin.site.site_header = "Granjimmy Hospital Psiquiátrico"
admin.site.site_title = "Painel Granjimmy"
admin.site.index_title = "Gestão de conteúdo"
