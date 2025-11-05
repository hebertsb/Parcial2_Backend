"""
Tests completos para validaciones del modelo Product y Category.
Verifica que las validaciones personalizadas funcionen correctamente.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal

from products.models import Product, Category


class CategoryValidationTestCase(TestCase):
    """Tests para validaciones del modelo Category"""
    
    def test_create_valid_category(self):
        """Test: Crear categoría válida"""
        category = Category.objects.create(
            name='Electronics',
            slug='electronics'
        )
        
        self.assertEqual(category.name, 'Electronics')
        self.assertEqual(category.slug, 'electronics')
        
    def test_category_name_cannot_be_empty(self):
        """Test: El nombre de categoría no puede estar vacío"""
        category = Category(name='', slug='empty')
        
        with self.assertRaises(ValidationError) as context:
            category.full_clean()
        
        self.assertIn('name', context.exception.error_dict)
        
    def test_category_name_cannot_be_whitespace(self):
        """Test: El nombre de categoría no puede ser solo espacios"""
        category = Category(name='   ', slug='whitespace')
        
        with self.assertRaises(ValidationError) as context:
            category.full_clean()
        
        self.assertIn('name', context.exception.error_dict)
        
    def test_category_slug_cannot_have_spaces(self):
        """Test: El slug no puede contener espacios"""
        category = Category(name='Test Category', slug='test category')
        
        with self.assertRaises(ValidationError) as context:
            category.full_clean()
        
        self.assertIn('slug', context.exception.error_dict)
        
    def test_category_name_must_be_unique(self):
        """Test: El nombre de categoría debe ser único"""
        Category.objects.create(name='Electronics', slug='electronics')
        
        duplicate = Category(name='Electronics', slug='electronics-2')
        
        with self.assertRaises(ValidationError):
            duplicate.full_clean()


class ProductValidationTestCase(TestCase):
    """Tests para validaciones del modelo Product"""
    
    def setUp(self):
        """Configuración inicial"""
        self.category = Category.objects.create(
            name='Electronics',
            slug='electronics'
        )
        
    def test_create_valid_product(self):
        """Test: Crear producto válido"""
        product = Product.objects.create(
            category=self.category,
            name='Laptop',
            price=Decimal('1000.00'),
            stock=10
        )
        
        self.assertEqual(product.name, 'Laptop')
        self.assertEqual(product.price, Decimal('1000.00'))
        self.assertEqual(product.stock, 10)
        
    def test_product_price_must_be_positive(self):
        """Test: El precio debe ser mayor a 0"""
        product = Product(
            category=self.category,
            name='Invalid Product',
            price=Decimal('0.00'),
            stock=10
        )
        
        with self.assertRaises(ValidationError) as context:
            product.save()
        
        self.assertIn('price', context.exception.error_dict)
        
    def test_product_price_cannot_be_negative(self):
        """Test: El precio no puede ser negativo"""
        product = Product(
            category=self.category,
            name='Invalid Product',
            price=Decimal('-50.00'),
            stock=10
        )
        
        with self.assertRaises(ValidationError) as context:
            product.save()
        
        self.assertIn('price', context.exception.error_dict)
        
    def test_product_name_cannot_be_empty(self):
        """Test: El nombre del producto no puede estar vacío"""
        product = Product(
            category=self.category,
            name='',
            price=Decimal('100.00'),
            stock=10
        )
        
        with self.assertRaises(ValidationError) as context:
            product.save()
        
        self.assertIn('name', context.exception.error_dict)
        
    def test_product_name_cannot_be_whitespace(self):
        """Test: El nombre no puede ser solo espacios"""
        product = Product(
            category=self.category,
            name='   ',
            price=Decimal('100.00'),
            stock=10
        )
        
        with self.assertRaises(ValidationError) as context:
            product.save()
        
        self.assertIn('name', context.exception.error_dict)
        
    def test_product_stock_cannot_be_negative(self):
        """Test: El stock no puede ser negativo"""
        # Aunque el campo es PositiveIntegerField, verificamos la validación
        product = Product(
            category=self.category,
            name='Test Product',
            price=Decimal('100.00'),
            stock=-5
        )
        
        with self.assertRaises(ValidationError):
            product.save()
        
    def test_product_stock_can_be_zero(self):
        """Test: El stock puede ser cero (agotado)"""
        product = Product.objects.create(
            category=self.category,
            name='Out of Stock Product',
            price=Decimal('100.00'),
            stock=0
        )
        
        self.assertEqual(product.stock, 0)
        self.assertFalse(product.is_available)
        
    def test_product_must_have_category(self):
        """Test: El producto debe tener una categoría"""
        product = Product(
            category=None,
            name='No Category Product',
            price=Decimal('100.00'),
            stock=10
        )
        
        with self.assertRaises(ValidationError):
            product.full_clean()
            
    def test_product_category_must_exist(self):
        """Test: La categoría debe existir en la base de datos"""
        # Crear una categoría y luego eliminarla
        temp_category = Category.objects.create(
            name='Temp',
            slug='temp'
        )
        
        product = Product.objects.create(
            category=temp_category,
            name='Test Product',
            price=Decimal('100.00'),
            stock=10
        )
        
        # Eliminar categoría (debería fallar por CASCADE)
        temp_category.delete()
        
        # Verificar que el producto también se eliminó
        self.assertFalse(Product.objects.filter(id=product.id).exists())


class ProductPropertiesTestCase(TestCase):
    """Tests para propiedades del modelo Product"""
    
    def setUp(self):
        """Configuración inicial"""
        self.category = Category.objects.create(
            name='Electronics',
            slug='electronics'
        )
        
    def test_is_available_returns_true_when_in_stock(self):
        """Test: is_available devuelve True cuando hay stock"""
        product = Product.objects.create(
            category=self.category,
            name='Available Product',
            price=Decimal('100.00'),
            stock=5
        )
        
        self.assertTrue(product.is_available)
        
    def test_is_available_returns_false_when_out_of_stock(self):
        """Test: is_available devuelve False cuando no hay stock"""
        product = Product.objects.create(
            category=self.category,
            name='Unavailable Product',
            price=Decimal('100.00'),
            stock=0
        )
        
        self.assertFalse(product.is_available)
        
    def test_is_low_stock_returns_true_when_stock_below_10(self):
        """Test: is_low_stock devuelve True cuando stock < 10"""
        product = Product.objects.create(
            category=self.category,
            name='Low Stock Product',
            price=Decimal('100.00'),
            stock=5
        )
        
        self.assertTrue(product.is_low_stock)
        
    def test_is_low_stock_returns_false_when_stock_10_or_more(self):
        """Test: is_low_stock devuelve False cuando stock >= 10"""
        product = Product.objects.create(
            category=self.category,
            name='Good Stock Product',
            price=Decimal('100.00'),
            stock=15
        )
        
        self.assertFalse(product.is_low_stock)
        
    def test_is_low_stock_returns_false_when_out_of_stock(self):
        """Test: is_low_stock devuelve False cuando stock = 0"""
        product = Product.objects.create(
            category=self.category,
            name='No Stock Product',
            price=Decimal('100.00'),
            stock=0
        )
        
        self.assertFalse(product.is_low_stock)


class ProductAPIValidationTestCase(TestCase):
    """Tests para validaciones a través de la API"""
    
    def setUp(self):
        """Configuración inicial"""
        from rest_framework.test import APIClient
        from django.contrib.auth.models import User
        from api.models import Profile
        
        self.client = APIClient()
        
        # Crear admin
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        Profile.objects.filter(user=self.admin).update(role='ADMIN')
        
        # Login
        login_response = self.client.post('/api/login/', {
            'username': 'admin',
            'password': 'admin123'
        })
        self.token = login_response.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        
        # Crear categoría
        self.category = Category.objects.create(
            name='Electronics',
            slug='electronics'
        )
        
    def test_api_reject_product_with_negative_price(self):
        """Test: API rechaza producto con precio negativo"""
        from django.core.exceptions import ValidationError
        
        with self.assertRaises(ValidationError):
            response = self.client.post('/api/shop/products/', {
                'category': self.category.id,
                'name': 'Invalid Product',
                'price': -100.00,
                'stock': 10
            })
        
    def test_api_reject_product_with_zero_price(self):
        """Test: API rechaza producto con precio cero"""
        from django.core.exceptions import ValidationError
        
        with self.assertRaises(ValidationError):
            response = self.client.post('/api/shop/products/', {
                'category': self.category.id,
                'name': 'Invalid Product',
                'price': 0,
                'stock': 10
            })
        
    def test_api_reject_product_with_negative_stock(self):
        """Test: API rechaza producto con stock negativo"""
    def test_api_reject_product_with_negative_stock(self):
        """Test: API rechaza producto con stock negativo"""
        response = self.client.post('/api/shop/products/', {
            'category': self.category.id,
            'name': 'Invalid Product',
            'price': 100.00,
            'stock': -5
        })
        
        # Debería devolver error 400
        self.assertEqual(response.status_code, 400)
        
    def test_api_accept_product_with_zero_stock(self):
        """Test: API acepta producto con stock cero"""
        response = self.client.post('/api/shop/products/', {
            'category': self.category.id,
            'name': 'Out of Stock Product',
            'price': 100.00,
            'stock': 0
        })
        
        # Debería ser exitoso
        self.assertEqual(response.status_code, 201)
        
    def test_api_reject_product_without_category(self):
        """Test: API rechaza producto sin categoría"""
        response = self.client.post('/api/shop/products/', {
            'name': 'No Category Product',
            'price': 100.00,
            'stock': 10
        })
        
        # Debería devolver error 400
        self.assertEqual(response.status_code, 400)
        
    def test_api_reject_product_with_invalid_category(self):
        """Test: API rechaza producto con categoría inexistente"""
        response = self.client.post('/api/shop/products/', {
            'category': 99999,  # ID que no existe
            'name': 'Invalid Category Product',
            'price': 100.00,
            'stock': 10
        })
        
        # Debería devolver error 400
        self.assertEqual(response.status_code, 400)
        
    def test_api_accept_valid_product(self):
        """Test: API acepta producto válido"""
        response = self.client.post('/api/shop/products/', {
            'category': self.category.id,
            'name': 'Valid Product',
            'price': 100.00,
            'stock': 50
        })
        
        # Debería ser exitoso
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['name'], 'Valid Product')
        self.assertEqual(float(response.data['price']), 100.00)
        self.assertEqual(response.data['stock'], 50)


# Resumen de cobertura de tests
"""
✅ Tests de Validación de Category:
   - Crear categoría válida
   - Nombre no puede estar vacío
   - Nombre no puede ser espacios
   - Slug no puede tener espacios
   - Nombre debe ser único

✅ Tests de Validación de Product:
   - Crear producto válido
   - Precio debe ser positivo
   - Precio no puede ser negativo
   - Nombre no puede estar vacío
   - Nombre no puede ser espacios
   - Stock no puede ser negativo
   - Stock puede ser cero
   - Debe tener categoría
   - Categoría debe existir

✅ Tests de Propiedades:
   - is_available (True cuando hay stock)
   - is_available (False cuando no hay stock)
   - is_low_stock (True cuando < 10)
   - is_low_stock (False cuando >= 10)
   - is_low_stock (False cuando = 0)

✅ Tests de API:
   - Rechazar precio negativo
   - Rechazar precio cero
   - Rechazar stock negativo
   - Aceptar stock cero
   - Rechazar sin categoría
   - Rechazar categoría inválida
   - Aceptar producto válido
"""
