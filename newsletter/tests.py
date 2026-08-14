"""Contratos da API pública: o que ela entrega e o que nunca deve vazar."""

import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from blog.models import Author, Category, Post
from newsletter.models import Subscriber


class ApiBlogTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cat = Category.objects.create(name="Saúde Mental")
        cls.autor = Author.objects.create(
            user=User.objects.create_user("dr.api"),
            display_name="Dr. API",
            credential="CRM-MT 0001",
        )
        for slug, status, quando in [
            ("rascunho", Post.Status.DRAFT, None),
            ("futuro", Post.Status.SCHEDULED, timezone.now() + datetime.timedelta(days=1)),
            ("no-ar", Post.Status.PUBLISHED, None),
        ]:
            Post.objects.create(
                title=slug, slug=slug, excerpt="resumo", content="conteudo",
                author=cls.autor, category=cls.cat, status=status, published_at=quando,
            )

    def test_lista_so_o_que_esta_no_ar(self):
        r = self.client.get("/api/v1/posts/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p["slug"] for p in r.json()["results"]], ["no-ar"])

    def test_card_tem_os_campos_do_cliente(self):
        card = self.client.get("/api/v1/posts/").json()["results"][0]
        self.assertLessEqual(
            {"title", "cover_image", "excerpt", "published_at", "author"}, set(card)
        )
        self.assertLessEqual(
            {"display_name", "photo", "credential"}, set(card["author"])
        )

    def test_detalhe_traz_conteudo(self):
        r = self.client.get("/api/v1/posts/no-ar/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["content"], "conteudo")

    def test_rascunho_e_inacessivel_por_slug(self):
        self.assertEqual(self.client.get("/api/v1/posts/rascunho/").status_code, 404)

    def test_health(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)


class ApiNewsletterTest(TestCase):
    URL = "/api/v1/newsletter/inscrever"

    def test_inscricao_nao_enumera_a_base(self):
        """E-mail novo e repetido devem responder igual, senão vaza quem está cadastrado."""
        a = self.client.post(self.URL, {"email": "x@teste.com"}, content_type="application/json")
        b = self.client.post(self.URL, {"email": "x@teste.com"}, content_type="application/json")
        self.assertEqual(a.status_code, 202)
        self.assertEqual((a.status_code, a.json()), (b.status_code, b.json()))

    def test_email_invalido(self):
        r = self.client.post(self.URL, {"email": "nao-e-email"}, content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_double_opt_in_e_descadastro(self):
        self.client.post(self.URL, {"email": "y@teste.com"}, content_type="application/json")
        sub = Subscriber.objects.get(email="y@teste.com")
        self.assertEqual(sub.status, Subscriber.Status.PENDING)

        self.assertEqual(
            self.client.get(f"/api/v1/newsletter/confirmar/{sub.token}").status_code, 200
        )
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscriber.Status.CONFIRMED)

        self.assertEqual(
            self.client.get(f"/api/v1/newsletter/descadastro/{sub.token}").status_code, 200
        )
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscriber.Status.UNSUBSCRIBED)

    def test_token_invalido(self):
        self.assertEqual(
            self.client.get("/api/v1/newsletter/confirmar/token-falso").status_code, 404
        )
