from rest_framework import serializers
from .models import Category, Product, Brand, Warranty, Offer
class OfferSerializer(serializers.ModelSerializer):
    products = serializers.PrimaryKeyRelatedField(many=True, queryset=Product.objects.all())

    class Meta:
        model = Offer
        fields = ['id', 'title', 'description', 'discount_percent', 'start_date', 'end_date', 'products', 'is_active']
import os


class WarrantySerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo de Garantías.
    """
    class Meta:
        model = Warranty
        fields = ['id', 'name', 'duration_days', 'details']


class BrandSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo de Marcas.
    """
    class Meta:
        model = Brand
        fields = ['id', 'name', 'is_active']


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo de Categorías.
    """
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo de Productos.
    """
    # Campos de solo lectura para info relacionada
    category_name = serializers.CharField(source='category.name', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True, allow_null=True)
    
    # Detalles de objetos relacionados
    category_detail = CategorySerializer(source='category', read_only=True)
    brand_detail = BrandSerializer(source='brand', read_only=True)
    warranty_detail = WarrantySerializer(source='warranty', read_only=True)

    image_url = serializers.SerializerMethodField()
    has_valid_image = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'description',
            'price',
            'stock',
            'category',
            'brand',
            'warranty', # ID para escritura
            'category_name',
            'brand_name',
            'category_detail',
            'brand_detail',
            'warranty_detail',
            'image',
            'image_url',
            'has_valid_image',
            'created_at',
            'updated_at'
        ]
    
    def get_image_url(self, obj):
        if obj.image:
            try:
                if os.path.isfile(obj.image.path):
                    request = self.context.get('request')
                    if request:
                        return request.build_absolute_uri(obj.image.url)
                    return obj.image.url
            except (ValueError, AttributeError, FileNotFoundError):
                pass
        return None
    
    def validate_image(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("La imagen no debe superar 5MB")
            
            valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
            ext = os.path.splitext(value.name)[1].lower()
            if ext not in valid_extensions:
                raise serializers.ValidationError(
                    f"Formato de imagen no válido. Use: {', '.join(valid_extensions)}"
                )
        return value
    
    def update(self, instance, validated_data):
        if 'image' in validated_data and validated_data['image']:
            if instance.image:
                try:
                    if os.path.isfile(instance.image.path):
                        os.remove(instance.image.path)
                except Exception:
                    pass
        return super().update(instance, validated_data)