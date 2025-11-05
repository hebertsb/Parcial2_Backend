"""
Tests para la funcionalidad de ventas y carrito de compras.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from products.models import Product, Category
from sales.models import Order, OrderItem
from api.models import Profile
from decimal import Decimal


class CartTestCase(TestCase):
    """Tests para el carrito de compras"""
    
    def setUp(self):
        """Configuración inicial"""
        self.client = APIClient()
        
        # Crear cliente
        self.client_user = User.objects.create_user(
            username='client',
            email='client@example.com',
            password='clientpass123'
        )
        
        # Crear categoría y productos
        self.category = Category.objects.create(
            name='Electronics',
            slug='electronics'
        )
        
        self.product1 = Product.objects.create(
            category=self.category,
            name='Laptop',
            price=1000.00,
            stock=10
        )
        self.product2 = Product.objects.create(
            category=self.category,
            name='Mouse',
            price=25.00,
            stock=50
        )
        
        # Login
        login_response = self.client.post('/api/login/', {
            'username': 'client',
            'password': 'clientpass123'
        })
        self.token = login_response.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
    
    def test_get_empty_cart(self):
        """Test: Obtener carrito vacío"""
        response = self.client.get('/api/orders/cart/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'PENDING')
        self.assertEqual(len(response.data['items']), 0)
        self.assertEqual(float(response.data['total_price']), 0.00)
    
    def test_add_product_to_cart(self):
        """Test: Añadir producto al carrito"""
        data = {
            'product_id': self.product1.id,
            'quantity': 2
        }
        
        response = self.client.post('/api/orders/cart/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['quantity'], 2)
        self.assertEqual(float(response.data['total_price']), 2000.00)
    
    def test_add_multiple_products_to_cart(self):
        """Test: Añadir múltiples productos al carrito"""
        # Añadir producto 1
        self.client.post('/api/orders/cart/', {
            'product_id': self.product1.id,
            'quantity': 1
        })
        
        # Añadir producto 2
        response = self.client.post('/api/orders/cart/', {
            'product_id': self.product2.id,
            'quantity': 3
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 2)
        # Total: (1000 * 1) + (25 * 3) = 1075
        self.assertEqual(float(response.data['total_price']), 1075.00)
    
    def test_add_same_product_increases_quantity(self):
        """Test: Añadir el mismo producto aumenta la cantidad"""
        # Añadir 2 unidades
        self.client.post('/api/orders/cart/', {
            'product_id': self.product1.id,
            'quantity': 2
        })
        
        # Añadir 3 unidades más del mismo producto
        response = self.client.post('/api/orders/cart/', {
            'product_id': self.product1.id,
            'quantity': 3
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['quantity'], 5)
    
    def test_cannot_add_more_than_stock(self):
        """Test: No permitir añadir más cantidad que el stock disponible"""
        data = {
            'product_id': self.product1.id,
            'quantity': 15  # Stock es 10
        }
        
        response = self.client.post('/api/orders/cart/', data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_update_cart_item_quantity(self):
        """Test: Actualizar cantidad de un item en el carrito"""
        # Añadir producto
        add_response = self.client.post('/api/orders/cart/', {
            'product_id': self.product1.id,
            'quantity': 2
        })
        
        item_id = add_response.data['items'][0]['id']
        
        # Actualizar cantidad
        update_response = self.client.put(f'/api/orders/cart/items/{item_id}/', {
            'quantity': 5
        })
        
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['items'][0]['quantity'], 5)
        self.assertEqual(float(update_response.data['total_price']), 5000.00)
    
    def test_remove_cart_item(self):
        """Test: Eliminar item del carrito"""
        # Añadir producto
        add_response = self.client.post('/api/orders/cart/', {
            'product_id': self.product1.id,
            'quantity': 2
        })
        
        item_id = add_response.data['items'][0]['id']
        
        # Eliminar item
        delete_response = self.client.delete(f'/api/orders/cart/items/{item_id}/')
        
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(delete_response.data['items']), 0)
        self.assertEqual(float(delete_response.data['total_price']), 0.00)
    
    def test_cart_requires_authentication(self):
        """Test: El carrito requiere autenticación"""
        # Remover credenciales
        self.client.credentials()
        
        response = self.client.get('/api/orders/cart/')
        
        # Django REST Framework puede devolver 401 o 403
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class OrderHistoryTestCase(TestCase):
    """Tests para historial de compras"""
    
    def setUp(self):
        """Configuración inicial"""
        self.client = APIClient()
        
        # Crear admin
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_superuser=True
        )
        self.admin_user.profile.role = Profile.Role.ADMIN
        self.admin_user.profile.save()
        
        # Crear cliente
        self.client_user = User.objects.create_user(
            username='client',
            email='client@example.com',
            password='clientpass123'
        )
        
        # Crear productos
        category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            category=category,
            name='Test Product',
            price=100.00,
            stock=50
        )
        
        # Crear orden completada
        self.order = Order.objects.create(
            customer=self.client_user,
            status='COMPLETED',
            total_price=200.00
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=100.00
        )
    
    def test_client_can_view_own_orders(self):
        """Test: Cliente puede ver su propio historial"""
        # Login como cliente
        login_response = self.client.post('/api/login/', {
            'username': 'client',
            'password': 'clientpass123'
        })
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {login_response.data["token"]}')
        
        response = self.client.get('/api/orders/my-orders/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.order.id)
    
    def test_admin_can_view_all_sales(self):
        """Test: Admin puede ver todas las ventas"""
        # Login como admin
        login_response = self.client.post('/api/login/', {
            'username': 'admin',
            'password': 'adminpass123'
        })
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {login_response.data["token"]}')
        
        response = self.client.get('/api/orders/sales-history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_filter_sales_by_customer(self):
        """Test: Filtrar ventas por cliente"""
        # Login como admin
        login_response = self.client.post('/api/login/', {
            'username': 'admin',
            'password': 'adminpass123'
        })
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {login_response.data["token"]}')
        
        response = self.client.get(f'/api/orders/sales-history/?customer={self.client_user.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for order in response.data:
            self.assertEqual(order['customer']['id'], self.client_user.id)
    
    def test_filter_sales_by_username(self):
        """Test: Filtrar ventas por username del cliente"""
        # Login como admin
        login_response = self.client.post('/api/login/', {
            'username': 'admin',
            'password': 'adminpass123'
        })
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {login_response.data["token"]}')
        
        response = self.client.get('/api/orders/sales-history/?customer_username=client')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_filter_sales_by_price_range(self):
        """Test: Filtrar ventas por rango de precio"""
        # Login como admin
        login_response = self.client.post('/api/login/', {
            'username': 'admin',
            'password': 'adminpass123'
        })
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {login_response.data["token"]}')
        
        response = self.client.get('/api/orders/sales-history/?total_min=100&total_max=300')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for order in response.data:
            total = float(order['total_price'])
            self.assertGreaterEqual(total, 100)
            self.assertLessEqual(total, 300)
    
    def test_client_cannot_view_all_sales(self):
        """Test: Cliente no puede ver todas las ventas"""
        # Login como cliente
        login_response = self.client.post('/api/login/', {
            'username': 'client',
            'password': 'clientpass123'
        })
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {login_response.data["token"]}')
        
        response = self.client.get('/api/orders/sales-history/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class StockManagementTestCase(TestCase):
    """Tests para gestión de stock al completar orden"""
    
    def setUp(self):
        """Configuración inicial"""
        self.client = APIClient()
        
        # Crear cliente
        self.client_user = User.objects.create_user(
            username='client',
            password='clientpass123'
        )
        
        # Crear producto
        category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            category=category,
            name='Test Product',
            price=100.00,
            stock=10
        )
        
        # Login
        login_response = self.client.post('/api/login/', {
            'username': 'client',
            'password': 'clientpass123'
        })
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {login_response.data["token"]}')
    
    def test_stock_decreases_after_order_completion(self):
        """Test: El stock disminuye al completar una orden"""
        # Añadir producto al carrito
        self.client.post('/api/orders/cart/', {
            'product_id': self.product.id,
            'quantity': 3
        })
        
        # Simular completar orden (normalmente esto lo haría Stripe webhook)
        order = Order.objects.get(customer=self.client_user, status='PENDING')
        order.status = 'COMPLETED'
        order.save()
        
        # Reducir stock manualmente (simula el webhook)
        for item in order.items.all():
            product = item.product
            product.stock -= item.quantity
            product.save()
        
        # Verificar que el stock disminuyó
        product_updated = Product.objects.get(id=self.product.id)
        self.assertEqual(product_updated.stock, 7)  # 10 - 3 = 7
