from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from .models import Author, Category, Post, Tag
from .serializers import (
    AuthorSerializer,
    CategorySerializer,
    PostDetailSerializer,
    PostListSerializer,
    TagSerializer,
)


class PostViewSet(viewsets.ReadOnlyModelViewSet):
    """API pública do blog. Expõe somente posts publicados e já no ar."""

    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category__slug", "author__slug", "tags__slug"]
    search_fields = ["title", "excerpt", "content"]
    ordering_fields = ["published_at", "title"]
    ordering = ["-published_at"]

    def get_queryset(self):
        return (
            Post.objects.published()
            .select_related("author", "category")
            .prefetch_related("tags")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PostDetailSerializer
        return PostListSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(active=True)
    serializer_class = CategorySerializer
    lookup_field = "slug"


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    lookup_field = "slug"


class AuthorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Author.objects.filter(active=True)
    serializer_class = AuthorSerializer
    lookup_field = "slug"
