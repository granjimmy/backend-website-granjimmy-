"""Fluxo editorial e travas de permissão do painel."""

import datetime
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from blog.admin import PostAdmin, is_editor
from blog.models import Author, Category, Post

SENHA = "SenhaDeTeste#2026"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("criar_grupos", stdout=StringIO())
        cls.cat = Category.objects.create(name="Saúde Mental")

        cls.user = User.objects.create_user("dr.teste", is_staff=True, password=SENHA)
        cls.user.groups.add(Group.objects.get(name="Médicos"))
        cls.autor = Author.objects.create(user=cls.user, display_name="Dr. Teste")

        cls.outro_user = User.objects.create_user("dra.outra", is_staff=True, password=SENHA)
        cls.outro_user.groups.add(Group.objects.get(name="Médicos"))
        cls.outro = Author.objects.create(user=cls.outro_user, display_name="Dra. Outra")

    def post(self, slug, status, quando=None, dono=None):
        return Post.objects.create(
            title=slug, slug=slug, excerpt="x", content="y",
            author=dono or self.autor, category=self.cat, status=status, published_at=quando,
        )


class FluxoEditorialTest(Base):
    def test_rascunho_nao_aparece(self):
        self.assertFalse(self.post("rascunho", Post.Status.DRAFT).is_visible)

    def test_agendado_futuro_nao_aparece(self):
        amanha = timezone.now() + datetime.timedelta(days=1)
        self.assertFalse(self.post("futuro", Post.Status.SCHEDULED, amanha).is_visible)

    def test_publicado_sem_data_recebe_data(self):
        p = self.post("pub", Post.Status.PUBLISHED)
        self.assertIsNotNone(p.published_at)
        self.assertTrue(p.is_visible)

    def test_comando_publica_agendado_vencido(self):
        atras = timezone.now() - datetime.timedelta(minutes=5)
        p = self.post("vencido", Post.Status.SCHEDULED, atras)
        call_command("publicar_agendados", "--no-email", stdout=StringIO())
        p.refresh_from_db()
        self.assertEqual(p.status, Post.Status.PUBLISHED)

    def test_newsletter_nao_reenvia(self):
        from newsletter.models import Subscriber

        Subscriber.objects.create(email="a@teste.com", status=Subscriber.Status.CONFIRMED)
        p = self.post("pub", Post.Status.PUBLISHED)

        call_command("publicar_agendados", stdout=StringIO())
        p.refresh_from_db()
        primeira = p.newsletter_sent_at
        self.assertIsNotNone(primeira)

        call_command("publicar_agendados", stdout=StringIO())
        p.refresh_from_db()
        self.assertEqual(p.newsletter_sent_at, primeira)


class TravasDoMedicoTest(Base):
    """As travas valem no servidor, não só na interface: POST forjado é recusado."""

    CAMPOS = {
        "excerpt": "x", "content": "y", "published_at_0": "", "published_at_1": "",
        "cover_alt": "", "meta_title": "", "meta_description": "", "tags": [],
        "_save": "Salvar",
    }

    def setUp(self):
        self.client.login(username="dr.teste", password=SENHA)

    def payload(self, **extra):
        return {**self.CAMPOS, "category": self.cat.id, **extra}

    def test_nao_publica_direto(self):
        self.client.post(
            "/painel/blog/post/add/",
            self.payload(title="forjado", slug="forjado", status="published"),
            follow=True,
        )
        p = Post.objects.filter(slug="forjado").first()
        self.assertTrue(p is None or p.status != Post.Status.PUBLISHED)

    def test_nao_assina_por_outro(self):
        self.client.post(
            "/painel/blog/post/add/",
            self.payload(title="autor", slug="autor", status="draft", author=self.outro.id),
            follow=True,
        )
        p = Post.objects.get(slug="autor")
        self.assertEqual(p.author_id, self.autor.id)

    def test_nao_acessa_post_alheio(self):
        alheio = self.post("alheio", Post.Status.DRAFT, dono=self.outro)
        r = self.client.get(f"/painel/blog/post/{alheio.id}/change/")
        self.assertIn(r.status_code, (302, 403))

    def test_post_no_ar_e_somente_leitura(self):
        p = self.post("no-ar", Post.Status.PUBLISHED)
        r = self.client.get(f"/painel/blog/post/{p.id}/change/")
        self.assertNotIn('name="_save"', r.content.decode())

        self.client.post(
            f"/painel/blog/post/{p.id}/change/",
            self.payload(title="ALTERADO", slug=p.slug, status="published"),
            follow=True,
        )
        p.refresh_from_db()
        self.assertEqual(p.title, "no-ar")

    def test_nao_acessa_inscritos(self):
        r = self.client.get("/painel/newsletter/subscriber/")
        self.assertIn(r.status_code, (302, 403))

    def test_listagem_traz_so_os_proprios(self):
        self.post("meu", Post.Status.DRAFT)
        self.post("dela", Post.Status.DRAFT, dono=self.outro)
        qs = PostAdmin(Post, None).get_queryset(type("R", (), {"user": self.user})())
        self.assertEqual([p.author_id for p in qs], [self.autor.id])

    def test_medico_nao_e_editor(self):
        self.assertFalse(is_editor(self.user))
