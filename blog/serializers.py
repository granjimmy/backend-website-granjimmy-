from rest_framework import serializers

from .models import Author, Category, Post, Tag


class AuthorSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()

    class Meta:
        model = Author
        fields = ("id", "display_name", "slug", "credential", "specialty", "bio", "photo")

    def get_photo(self, obj):
        if not obj.photo:
            return None
        request = self.context.get("request")
        url = obj.photo.url
        return request.build_absolute_uri(url) if request else url


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description")


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "slug")


class PostListSerializer(serializers.ModelSerializer):
    """Card da listagem: título, imagem, breve descrição, data, autor e foto."""

    author = AuthorSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "title",
            "slug",
            "excerpt",
            "cover_image",
            "cover_alt",
            "published_at",
            "author",
            "category",
        )

    def get_cover_image(self, obj):
        if not obj.cover_image:
            return None
        request = self.context.get("request")
        url = obj.cover_image.url
        return request.build_absolute_uri(url) if request else url


class PostDetailSerializer(PostListSerializer):
    tags = TagSerializer(many=True, read_only=True)

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + (
            "content",
            "tags",
            "meta_title",
            "meta_description",
            "updated",
        )
