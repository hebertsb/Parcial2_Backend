"""
Generador de datos sintéticos para demostración del sistema de predicción de ventas.
Crea ventas realistas con patrones estacionales, tendencias y variabilidad.
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from products.models import Product, Category
from sales.models import Order, OrderItem

User = get_user_model()


class SalesDataGenerator:
    """
    Genera datos sintéticos de ventas con patrones realistas.
    """
    
    def __init__(self):
        self.start_date = timezone.now() - timedelta(days=540)  # 18 meses atrás
        self.end_date = timezone.now()
        
    def _create_demo_products_if_needed(self) -> List[Product]:
        """Crea productos de demo si no existen."""
        # Verificar si ya hay productos
        if Product.objects.count() >= 10:
            return list(Product.objects.all()[:10])
        
        # Crear categorías demo
        categories_data = [
            {'name': 'Electrónica', 'slug': 'electronica'},
            {'name': 'Ropa', 'slug': 'ropa'},
            {'name': 'Hogar', 'slug': 'hogar'},
            {'name': 'Deportes', 'slug': 'deportes'},
        ]
        
        categories = []
        for cat_data in categories_data:
            category, _ = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={'name': cat_data['name']}
            )
            categories.append(category)
        
        # Crear productos demo
        products_data = [
            {'name': 'Laptop Dell', 'price': 1200.00, 'category': categories[0], 'popularity': 0.9},
            {'name': 'Mouse Inalámbrico', 'price': 25.00, 'category': categories[0], 'popularity': 0.8},
            {'name': 'Teclado Mecánico', 'price': 150.00, 'category': categories[0], 'popularity': 0.7},
            {'name': 'Camiseta Nike', 'price': 35.00, 'category': categories[1], 'popularity': 0.6},
            {'name': 'Pantalón Jean', 'price': 50.00, 'category': categories[1], 'popularity': 0.5},
            {'name': 'Cafetera', 'price': 80.00, 'category': categories[2], 'popularity': 0.7},
            {'name': 'Aspiradora', 'price': 200.00, 'category': categories[2], 'popularity': 0.4},
            {'name': 'Pelota de Fútbol', 'price': 30.00, 'category': categories[3], 'popularity': 0.6},
            {'name': 'Bicicleta', 'price': 500.00, 'category': categories[3], 'popularity': 0.3},
            {'name': 'Auriculares', 'price': 75.00, 'category': categories[0], 'popularity': 0.8},
        ]
        
        products = []
        for prod_data in products_data:
            product, created = Product.objects.get_or_create(
                name=prod_data['name'],
                defaults={
                    'price': Decimal(str(prod_data['price'])),
                    'category': prod_data['category'],
                    'stock': 1000,
                    'description': f"Producto demo: {prod_data['name']}"
                }
            )
            # Guardar popularidad para uso interno
            product._popularity = prod_data['popularity']
            products.append(product)
        
        return products
    
    def _create_demo_customers_if_needed(self) -> List[User]:
        """Crea clientes de demo si no existen."""
        # Verificar si ya hay clientes
        clients = list(User.objects.filter(profile__role='CLIENT')[:5])
        if len(clients) >= 5:
            return clients
        
        # Crear clientes demo
        customers_data = [
            {'username': 'cliente1', 'email': 'cliente1@demo.com', 'first_name': 'Juan', 'last_name': 'Pérez'},
            {'username': 'cliente2', 'email': 'cliente2@demo.com', 'first_name': 'María', 'last_name': 'García'},
            {'username': 'cliente3', 'email': 'cliente3@demo.com', 'first_name': 'Carlos', 'last_name': 'López'},
            {'username': 'cliente4', 'email': 'cliente4@demo.com', 'first_name': 'Ana', 'last_name': 'Martínez'},
            {'username': 'cliente5', 'email': 'cliente5@demo.com', 'first_name': 'Luis', 'last_name': 'Rodríguez'},
        ]
        
        customers = []
        for cust_data in customers_data:
            user, created = User.objects.get_or_create(
                username=cust_data['username'],
                defaults={
                    'email': cust_data['email'],
                    'first_name': cust_data['first_name'],
                    'last_name': cust_data['last_name'],
                }
            )
            if created:
                user.set_password('demo123')
                user.save()
                # Asegurar que tenga perfil
                if not hasattr(user, 'profile'):
                    from api.models import Profile
                    Profile.objects.create(user=user, role='CLIENT')
            customers.append(user)
        
        return customers
    
    def _get_seasonal_multiplier(self, date: datetime) -> float:
        """
        Calcula un multiplicador estacional basado en el mes.
        - Diciembre (12): Alto (navidad)
        - Enero-Febrero: Bajo (post navidad)
        - Julio: Alto (medio año)
        - Resto: Normal
        """
        month = date.month
        
        if month == 12:
            return 1.5  # Pico navideño
        elif month in [1, 2]:
            return 0.7  # Bajón post navidad
        elif month in [7, 8]:
            return 1.3  # Temporada media alta
        elif month in [6, 11]:
            return 1.2  # Pre-vacaciones y pre-navidad
        else:
            return 1.0  # Normal
    
    def _get_trend_multiplier(self, date: datetime) -> float:
        """
        Calcula un multiplicador de tendencia (crecimiento en el tiempo).
        Simula crecimiento del negocio.
        """
        days_from_start = (date - self.start_date).days
        total_days = (self.end_date - self.start_date).days
        progress = days_from_start / total_days
        
        # Crecimiento del 50% durante el período
        return 1.0 + (progress * 0.5)
    
    def _get_weekday_multiplier(self, date: datetime) -> float:
        """
        Calcula multiplicador según día de la semana.
        - Fin de semana: Más ventas
        - Días laborables: Ventas normales
        """
        weekday = date.weekday()
        
        if weekday in [5, 6]:  # Sábado y Domingo
            return 1.3
        elif weekday == 4:  # Viernes
            return 1.1
        else:
            return 1.0
    
    def _generate_daily_sales_count(self, date: datetime) -> int:
        """
        Calcula cuántas ventas generar para un día específico.
        """
        # Base: 5-15 ventas por día
        base_sales = random.randint(5, 15)
        
        # Aplicar multiplicadores
        seasonal = self._get_seasonal_multiplier(date)
        trend = self._get_trend_multiplier(date)
        weekday = self._get_weekday_multiplier(date)
        
        # Variabilidad aleatoria (80%-120%)
        random_factor = random.uniform(0.8, 1.2)
        
        # Calcular ventas finales
        sales_count = int(base_sales * seasonal * trend * weekday * random_factor)
        
        return max(1, sales_count)  # Mínimo 1 venta
    
    def _generate_order_items(self, products: List[Product]) -> List[Dict[str, Any]]:
        """
        Genera items para una orden, considerando popularidad de productos.
        """
        # Número de items por orden (1-4)
        num_items = random.choices([1, 2, 3, 4], weights=[0.5, 0.3, 0.15, 0.05])[0]
        
        # Seleccionar productos según popularidad
        selected_products = random.choices(
            products,
            weights=[getattr(p, '_popularity', 0.5) for p in products],
            k=num_items
        )
        
        items = []
        for product in selected_products:
            quantity = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
            items.append({
                'product': product,
                'quantity': quantity,
                'price': product.price
            })
        
        return items
    
    @transaction.atomic
    def generate_demo_data(self, clear_existing: bool = False) -> Dict[str, Any]:
        """
        Genera datos sintéticos de ventas.
        
        Args:
            clear_existing: Si es True, elimina las órdenes existentes antes de generar
            
        Returns:
            Dict con estadísticas de generación
        """
        if clear_existing:
            Order.objects.all().delete()
            print("✓ Órdenes existentes eliminadas")
        
        # Preparar datos
        products = self._create_demo_products_if_needed()
        customers = self._create_demo_customers_if_needed()
        
        print(f"✓ Usando {len(products)} productos y {len(customers)} clientes")
        
        # Generar ventas día por día
        current_date = self.start_date
        total_orders = 0
        total_revenue = Decimal('0.00')
        
        while current_date <= self.end_date:
            daily_sales = self._generate_daily_sales_count(current_date)
            
            for _ in range(daily_sales):
                # Seleccionar cliente aleatorio
                customer = random.choice(customers)
                
                # Generar items
                items_data = self._generate_order_items(products)
                
                # Calcular total
                order_total = sum(
                    Decimal(str(item['quantity'])) * item['price'] 
                    for item in items_data
                )
                
                # Fecha específica para esta orden
                order_date = current_date + timedelta(
                    hours=random.randint(8, 20),
                    minutes=random.randint(0, 59)
                )
                
                # Crear orden (auto_now_add pone la fecha actual, la actualizaremos después)
                order = Order.objects.create(
                    customer=customer,
                    total_price=order_total,
                    status='COMPLETED'
                )
                
                # Actualizar la fecha manualmente (by-passing auto_now_add)
                Order.objects.filter(pk=order.pk).update(
                    created_at=order_date,
                    updated_at=order_date
                )
                
                # Crear items de la orden
                for item_data in items_data:
                    OrderItem.objects.create(
                        order=order,
                        product=item_data['product'],
                        quantity=item_data['quantity'],
                        price=item_data['price']
                    )
                
                total_orders += 1
                total_revenue += order_total
            
            current_date += timedelta(days=1)
        
        print(f"✓ Generadas {total_orders} órdenes")
        print(f"✓ Ingresos totales: ${total_revenue:,.2f}")
        
        return {
            'total_orders': total_orders,
            'total_revenue': float(total_revenue),
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'end_date': self.end_date.strftime('%Y-%m-%d'),
            'products_count': len(products),
            'customers_count': len(customers)
        }


def generate_sales_data(clear_existing: bool = False) -> Dict[str, Any]:
    """
    Función helper para generar datos de ventas demo.
    
    Args:
        clear_existing: Si es True, elimina las órdenes existentes antes de generar
        
    Returns:
        Dict con estadísticas de generación
        
    Ejemplo:
        >>> from sales.ml_data_generator import generate_sales_data
        >>> stats = generate_sales_data(clear_existing=True)
        >>> print(stats)
    """
    generator = SalesDataGenerator()
    return generator.generate_demo_data(clear_existing=clear_existing)
