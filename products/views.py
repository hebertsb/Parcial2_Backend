from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Category, Product, Brand, Warranty, Offer
from .serializers import CategorySerializer, ProductSerializer, BrandSerializer, WarrantySerializer, OfferSerializer
class OfferViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar ofertas (CRUD).
    - GET: Público (listar/ver)
    - POST/PUT/PATCH/DELETE: Solo admin
    """
    queryset = Offer.objects.prefetch_related('products').all()
    serializer_class = OfferSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]
from .filters import ProductFilter
from api.permissions import IsAdminUser
import os

class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar categorías.
    - GET: Acceso público (lectura)
    - POST/PUT/DELETE: Solo administradores
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    
    def get_permissions(self):
        """
        Permisos dinámicos:
        - Lectura (GET, HEAD, OPTIONS): Público
        - Escritura (POST, PUT, PATCH, DELETE): Solo admins
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]
    
    # ✅ Cache de 5 minutos para reducir carga (solo en lectura)
    @method_decorator(cache_page(60 * 5))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class BrandViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar marcas.
    - GET: Acceso público
    - POST/PUT/DELETE: Solo administradores
    """
    queryset = Brand.objects.filter(is_active=True)
    serializer_class = BrandSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]


class WarrantyViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar garantías.
    - GET: Acceso público
    - POST/PUT/DELETE: Solo administradores
    """
    queryset = Warranty.objects.all()
    serializer_class = WarrantySerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]


class ProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestión completa de productos.
    
    PERMISOS:
    - GET (Lectura): Acceso público
    - POST/PUT/PATCH/DELETE (Escritura): Solo administradores
    
    Incluye filtros avanzados por categoría, precio, stock y búsqueda.
    
    Ejemplos de uso:
    - GET /api/shop/products/ - Listar todos los productos
    - GET /api/shop/products/3/ - Ver detalle de producto
    - PUT /api/shop/products/3/ - Actualizar producto (admin)
    - POST /api/shop/products/ - Crear producto (admin)
    - DELETE /api/shop/products/3/ - Eliminar producto (admin)
    
    Filtros:
    - /api/shop/products/?name=laptop (buscar por nombre)
    - /api/shop/products/?category_slug=electronics (filtrar por categoría)
    - /api/shop/products/?price_min=100&price_max=500 (rango de precio)
    - /api/shop/products/?in_stock=true (solo productos disponibles)
    - /api/shop/products/?ordering=-price (ordenar por precio descendente)
    """
    # ✅ OPTIMIZADO: select_related para traer la categoría en una sola consulta
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'name', 'stock']
    ordering = ['-created_at']  # Orden por defecto
    
    def get_permissions(self):
        """
        Permisos dinámicos:
        - Lectura (GET, HEAD, OPTIONS): Público
        - Escritura (POST, PUT, PATCH, DELETE): Solo admins
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]
    
    # ✅ Cache de 2 minutos para reducir carga (solo en lectura)
    @method_decorator(cache_page(60 * 2))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def upload_image(self, request, pk=None):
        """
        Endpoint personalizado para subir/actualizar imagen de un producto.
        POST /api/shop/products/{id}/upload_image/
        
        Body: FormData con campo 'image'
        """
        product = self.get_object()
        
        if 'image' not in request.FILES:
            return Response(
                {'error': 'No se proporcionó ninguna imagen. Use el campo "image".'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        image_file = request.FILES['image']
        
        # Validar tamaño (5MB máximo)
        if image_file.size > 5 * 1024 * 1024:
            return Response(
                {'error': 'La imagen no debe superar 5MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar extensión
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        ext = os.path.splitext(image_file.name)[1].lower()
        if ext not in valid_extensions:
            return Response(
                {'error': f'Formato no válido. Use: {", ".join(valid_extensions)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Eliminar imagen anterior si existe
        if product.image:
            try:
                if os.path.isfile(product.image.path):
                    os.remove(product.image.path)
            except Exception:
                pass
        
        # Guardar nueva imagen
        product.image = image_file
        product.save()
        
        serializer = self.get_serializer(product)
        return Response({
            'message': 'Imagen actualizada correctamente',
            'product': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['delete'], permission_classes=[IsAdminUser])
    def delete_image(self, request, pk=None):
        """
        Endpoint para eliminar la imagen de un producto.
        DELETE /api/shop/products/{id}/delete_image/
        """
        product = self.get_object()
        
        if not product.image:
            return Response(
                {'error': 'Este producto no tiene imagen'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Eliminar archivo físico
        try:
            if os.path.isfile(product.image.path):
                os.remove(product.image.path)
        except Exception as e:
            pass
        
        # Limpiar campo en BD
        product.image = None
        product.save()
        
        return Response(
            {'message': 'Imagen eliminada correctamente'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def clean_broken_images(self, request):
        """
        Endpoint para limpiar referencias a imágenes rotas en la BD.
        POST /api/shop/products/clean_broken_images/
        
        Revisa todos los productos y elimina referencias a imágenes que no existen.
        """
        products = Product.objects.exclude(image='').exclude(image=None)
        cleaned_count = 0
        
        for product in products:
            try:
                # Verificar si el archivo existe
                if not product.image or not hasattr(product.image, 'path') or not os.path.isfile(product.image.path):
                    # Imagen no existe físicamente, limpiar referencia
                    if product.image and hasattr(product.image, 'delete'):
                        product.image.delete(save=True)
                        cleaned_count += 1
            except (ValueError, AttributeError):
                # Error al acceder a la ruta, limpiar referencia
                if product.image and hasattr(product.image, 'delete'):
                    product.image.delete(save=True)
                    cleaned_count += 1
        
        return Response({
            'message': f'Limpieza completada. {cleaned_count} imagen(es) rota(s) eliminada(s).',
            'cleaned_count': cleaned_count
        }, status=status.HTTP_200_OK)
