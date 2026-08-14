from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from blog.views import AuthorViewSet, CategoryViewSet, PostViewSet, TagViewSet
from newsletter import views as news_views

router = DefaultRouter()
router.register("posts", PostViewSet, basename="post")
router.register("categorias", CategoryViewSet, basename="categoria")
router.register("tags", TagViewSet, basename="tag")
router.register("autores", AuthorViewSet, basename="autor")


def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("painel/", admin.site.urls),
    path("api/v1/", include(router.urls)),
    path("api/v1/newsletter/inscrever", news_views.subscribe, name="newsletter-subscribe"),
    path(
        "api/v1/newsletter/confirmar/<str:token>",
        news_views.confirm,
        name="newsletter-confirm",
    ),
    path(
        "api/v1/newsletter/descadastro/<str:token>",
        news_views.unsubscribe,
        name="newsletter-unsubscribe",
    ),
    path("api/health", health, name="health"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
