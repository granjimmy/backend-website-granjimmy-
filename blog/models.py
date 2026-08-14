"""Modelos do blog: autores (médicos), categorias e posts.

Fluxo editorial: rascunho -> agendado -> publicado.
Um post agendado só aparece na API quando published_at chega.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Author(models.Model):
    """Perfil público do médico que assina o post.

    Separado do User para que o dado editorial (nome de exibição, CRM, foto,
    bio) não se misture com a conta de acesso. Um médico pode existir como
    autor sem nunca logar (posts institucionais assinados por ele).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="author_profile",
        verbose_name="conta de acesso",
        help_text="Conta usada para login. Deixe em branco para autor sem acesso ao painel.",
    )
    display_name = models.CharField("nome de exibição", max_length=160)
    slug = models.SlugField("slug", max_length=180, unique=True, blank=True)
    credential = models.CharField(
        "registro profissional",
        max_length=120,
        blank=True,
        help_text="Ex.: CRM-MT 4687 / RQE 2756",
    )
    specialty = models.CharField("especialidade", max_length=160, blank=True)
    bio = models.TextField("minicurrículo", blank=True)
    # Requisito: a imagem do autor aparece no card da publicação.
    photo = models.ImageField("foto", upload_to="autores/", blank=True, null=True)
    email = models.EmailField("e-mail público", blank=True)
    active = models.BooleanField("ativo", default=True)
    created = models.DateTimeField("criado em", auto_now_add=True)
    updated = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "autor"
        verbose_name_plural = "autores"
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.display_name)[:180]
        super().save(*args, **kwargs)


class Category(models.Model):
    name = models.CharField("nome", max_length=120, unique=True)
    slug = models.SlugField("slug", max_length=140, unique=True, blank=True)
    description = models.TextField("descrição", blank=True)
    active = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)


class Tag(models.Model):
    name = models.CharField("nome", max_length=80, unique=True)
    slug = models.SlugField("slug", max_length=100, unique=True, blank=True)

    class Meta:
        verbose_name = "tag"
        verbose_name_plural = "tags"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:100]
        super().save(*args, **kwargs)


class PostQuerySet(models.QuerySet):
    def published(self):
        """Somente o que o público pode ver: publicado E com data já atingida.

        É esta condição que faz o agendamento funcionar sem worker/cron:
        o post agendado simplesmente entra no queryset quando a hora chega.
        """
        return self.filter(
            status=Post.Status.PUBLISHED,
            published_at__lte=timezone.now(),
        )


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        SCHEDULED = "scheduled", "Agendado"
        PUBLISHED = "published", "Publicado"

    # --- campos exibidos no card da publicação (requisito do cliente) ---
    title = models.CharField("título", max_length=220)
    slug = models.SlugField("slug", max_length=240, unique=True, blank=True)
    excerpt = models.TextField(
        "breve descrição",
        max_length=400,
        help_text="Resumo exibido na listagem e no e-mail da newsletter.",
    )
    cover_image = models.ImageField("imagem de capa", upload_to="blog/", blank=True, null=True)
    cover_alt = models.CharField(
        "texto alternativo da imagem",
        max_length=200,
        blank=True,
        help_text="Descrição da imagem para acessibilidade e SEO.",
    )
    author = models.ForeignKey(
        Author,
        on_delete=models.PROTECT,
        related_name="posts",
        verbose_name="autor",
    )
    published_at = models.DateTimeField(
        "data de publicação",
        null=True,
        blank=True,
        help_text="Data futura + status 'Agendado' publica automaticamente.",
    )
    # --- conteúdo ---
    content = models.TextField("conteúdo")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="posts",
        verbose_name="categoria",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts", verbose_name="tags")
    status = models.CharField(
        "situação",
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    # --- SEO ---
    meta_title = models.CharField("título SEO", max_length=200, blank=True)
    meta_description = models.CharField("descrição SEO", max_length=300, blank=True)
    # --- newsletter ---
    newsletter_sent_at = models.DateTimeField(
        "newsletter enviada em",
        null=True,
        blank=True,
        editable=False,
        help_text="Preenchido automaticamente. Garante que o post não seja notificado duas vezes.",
    )
    created = models.DateTimeField("criado em", auto_now_add=True)
    updated = models.DateTimeField("atualizado em", auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        verbose_name = "publicação"
        verbose_name_plural = "publicações"
        ordering = ["-published_at", "-created"]
        indexes = [
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:240]
        # Publicar sem informar a data preenche com "agora" — evita post
        # publicado que nunca aparece por published_at nulo.
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_visible(self):
        return (
            self.status == self.Status.PUBLISHED
            and self.published_at is not None
            and self.published_at <= timezone.now()
        )
