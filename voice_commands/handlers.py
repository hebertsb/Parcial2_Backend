import re
import logging
from typing import Dict, Any, List, Optional, cast
from django.db import transaction
from products.models import Product, Brand
from sales.models import Order, OrderItem

logger = logging.getLogger(__name__)


def _extract_quantity(text: str) -> int:
    m = re.search(r"(\d+)\s*(?:unidades|unidad|uds|ud|x)?", text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return 1
    return 1


def _extract_product_id(text: str) -> Optional[int]:
    # Busca patrones como id 123 o #123
    m = re.search(r"(?:id\s*|#)(\d{1,6})\b", text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def handle_search_products(text: str, limit: int = 10) -> Dict[str, Any]:
    """Busca productos por nombre en el catálogo."""
    # Extraer término de búsqueda: quitar palabras comunes
    terms = re.sub(r"\b(buscar|tienes|hay|mostrar|muéstrame|muestra|dame|quiero|ver|producto|productos)\b", "", text, flags=re.I)
    terms = terms.strip()
    qs = Product.objects.filter(name__icontains=terms) if terms else Product.objects.all()
    qs = qs.filter(stock__gt=0).order_by('-stock')[:limit]

    results = []
    for p in qs:
        # Ayuda para Pylance: los modelos Django añaden atributos dinámicos (id, fields)
        # casteamos a Any para evitar advertencias de análisis estático.
        p = cast(Any, p)
        results.append({
            'id': p.id,
            'name': p.name,
            'price': float(p.price),
            'stock': p.stock,
            'image_url': p.image_url
        })

    return {'success': True, 'query': terms, 'count': len(results), 'products': results}


def handle_recommend_products(user, text: str, limit: int = 5) -> Dict[str, Any]:
    """Recomendador simple por reglas (stock y categoría si se menciona)."""
    # Intent: si menciona categoría, usarla
    cat_match = re.search(r"categoria\s+de\s+(\w+)", text, flags=re.I)
    qs = Product.objects.filter(stock__gt=0)
    if cat_match:
        cat = cat_match.group(1)
        qs = qs.filter(category__name__icontains=cat)

    # Si el usuario menciona una marca explícita (p. ej. 'LG'), filtramos por esa marca
    try:
        text_low = text.lower()
        for b in Brand.objects.filter(is_active=True):
            if b.name and b.name.lower() in text_low:
                qs = qs.filter(brand=b)
                break
    except Exception:
        # Silenciar errores de consulta de marcas en entornos de test sencillos
        pass

    qs = qs.order_by('-stock', '-created_at')[:limit]
    recs = []
    for p in qs:
        p = cast(Any, p)
        recs.append({'id': p.id, 'name': p.name, 'price': float(p.price), 'stock': p.stock, 'image_url': p.image_url})

    return {'success': True, 'count': len(recs), 'recommendations': recs}


def handle_add_to_cart(user, text: str, product_id: Optional[int] = None, quantity: Optional[int] = None) -> Dict[str, Any]:
    """Añade un producto al carrito (Order PENDING)."""
    # Determinar cantidad y producto
    qty = quantity or _extract_quantity(text)
    pid = product_id or _extract_product_id(text)

    product = None
    if pid:
        try:
            product = Product.objects.get(pk=pid)
            product = cast(Any, product)
        except Product.DoesNotExist:
            return {'success': False, 'error': 'Producto no encontrado por id'}
    else:
        # Intentar buscar por nombre en el texto (palabras clave)
        # Tomar las palabras luego de 'añade' o 'agrega' o 'comprar'
        m = re.search(r"(?:añad[ea]|agreg[ae]|comprar|comprarme)\s+(.*)", text, flags=re.I)
        term = m.group(1) if m else text
        term = re.sub(r"\b(al carrito|alcarrito|al carrito|alcarrito|al carrito)\b", "", term, flags=re.I).strip()
        qs = Product.objects.filter(name__icontains=term)
        if not qs.exists():
            # fallback: primer producto que contenga cualquiera de las palabras
            tokens = [t for t in re.split(r"\s+", term) if len(t) > 2]
            if tokens:
                q = Product.objects.none()
                for tk in tokens:
                    q = q | Product.objects.filter(name__icontains=tk)
                qs = q.distinct()

        if not qs.exists():
            return {'success': False, 'error': 'No pude encontrar el producto mencionado'}
        product = qs.first()
        product = cast(Any, product)

    # Validar stock (no reservar, solo informar)
    if product is None:
        return {'success': False, 'error': 'Producto no encontrado'}

    if product.stock < qty:
        return {'success': False, 'error': f'Stock insuficiente ({product.stock} disponibles)'}

    # Obtener o crear carrito
    order, _ = Order.objects.get_or_create(customer=user, status=Order.OrderStatus.PENDING)
    order = cast(Any, order)

    with transaction.atomic():
        item, created = OrderItem.objects.get_or_create(order=order, product=product, defaults={'quantity': qty, 'price': product.price})
        if not created:
            item.quantity += qty
            item.save()

        # Actualizar total
        # order.items es un related_name; casteamos order a Any arriba para evitar advertencias estáticas
        total = sum(i.quantity * i.price for i in order.items.all())
        order.total_price = total
        order.save()

    return {'success': True, 'order_id': order.id, 'product_id': product.id, 'quantity': item.quantity}
