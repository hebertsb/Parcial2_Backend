from rest_framework import serializers
from .models import Category, Product
import os


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
    
    CAMPOS:
    - category: ID de la categoría (lectura y escritura)
    - category_name: Nombre de la categoría (solo lectura, para mostrar)
    - category_slug: Slug de la categoría (solo lectura, para filtros)
    - category_detail: Objeto completo de categoría (solo lectura, para formularios)
    - image: Archivo de imagen (puede ser null)
    - image_url: URL segura de la imagen (null si no existe físicamente)
    - has_valid_image: Indica si la imagen existe y es válida
    """
    # Para mostrar información adicional de la categoría (solo lectura)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.SlugField(source='category.slug', read_only=True)
    
    # ✅ NUEVO: Devolver el objeto completo de categoría para el frontend
    category_detail = CategorySerializer(source='category', read_only=True)
    
    # ✅ NUEVO: URL segura de imagen que valida existencia física
    image_url = serializers.SerializerMethodField()
    has_valid_image = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id',
            'category',           # ✅ ID para lectura/escritura
            'category_name',      # Solo lectura: nombre de categoría
            'category_slug',      # Solo lectura: slug de categoría
            'category_detail',    # ✅ NUEVO: Objeto completo para formularios
            'name',
            'description',
            'price',
            'stock',
            'image',              # Campo de imagen (puede ser null)
            'image_url',          # ✅ URL validada de la imagen
            'has_valid_image',    # ✅ Indica si tiene imagen válida
            'created_at',
            'updated_at'
        ]
    
    def get_image_url(self, obj):
        """
        Devuelve la URL de la imagen solo si existe físicamente.
        Evita errores 404 en el frontend.
        """
        if obj.image:
            try:
                # Verificar si el archivo existe
                if os.path.isfile(obj.image.path):
                    request = self.context.get('request')
                    if request:
                        return request.build_absolute_uri(obj.image.url)
                    return obj.image.url
            except (ValueError, AttributeError, FileNotFoundError):
                pass
        return None
    
    def validate_image(self, value):
        """
        Valida el archivo de imagen subido
        """
        if value:
            # Validar tamaño (máximo 5MB)
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("La imagen no debe superar 5MB")
            
            # Validar tipo de archivo
            valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
            ext = os.path.splitext(value.name)[1].lower()
            if ext not in valid_extensions:
                raise serializers.ValidationError(
                    f"Formato de imagen no válido. Use: {', '.join(valid_extensions)}"
                )
        
        return value
    
    def update(self, instance, validated_data):
        """
        Actualización personalizada para manejar imágenes correctamente
        """
        # Si se envía una nueva imagen, eliminar la anterior
        if 'image' in validated_data and validated_data['image']:
            if instance.image:
                try:
                    # Eliminar imagen anterior si existe
                    if os.path.isfile(instance.image.path):
                        os.remove(instance.image.path)
                except Exception:
                    pass
        
        return super().update(instance, validated_data)