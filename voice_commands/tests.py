from typing import Any, cast
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from products.models import Category, Brand, Product


class ChatbotRecommendTest(TestCase):
    """Test simple: cliente pide recomendación y el chatbot devuelve productos."""

    def setUp(self):
        User = get_user_model()
        # Pylance no siempre reconoce métodos añadidos al manager por apps, casteamos a Any
        user_manager = cast(Any, getattr(User, 'objects'))

        self.user = user_manager.create_user(username='testuser', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        # Crear datos mínimos: categoría, marca y productos
        self.cat = Category.objects.create(name='Heladeras', slug='heladeras')
        self.brand_lg = Brand.objects.create(name='LG')
        self.brand_samsung = Brand.objects.create(name='Samsung')

        Product.objects.create(category=self.cat, brand=self.brand_lg, name='LG Heladera 300L', price='1200.00', stock=5)
        Product.objects.create(category=self.cat, brand=self.brand_samsung, name='Samsung Fridge X', price='1100.00', stock=3)

    def test_chat_recommend_heladera(self):
        """Pedir recomendación de una heladera debe retornar intent 'recommend' y recomendaciones."""
        payload = {'text': '¿me recomiendas una heladera para la casa?'}
        resp = self.client.post('/api/voice-commands/chat/process/', payload, format='json')
        self.assertIn(resp.status_code, (200, 202))
        body = resp.json()
        self.assertTrue(body.get('success'))
        self.assertEqual(body.get('intent'), 'recommend')

        # Normalizar accessos: garantizar que result y recommendations sean colecciones
        result = body.get('result') or {}
        recs = result.get('recommendations') if isinstance(result, dict) else []
        if recs is None:
            recs = []

        self.assertIsInstance(recs, list)
        self.assertGreaterEqual(len(recs), 1)

        # Asegurar que una recomendación incluya 'LG' o 'heladera' en el nombre
        names = [(r.get('name') or '').lower() for r in recs if isinstance(r, dict)]
        self.assertTrue(any('lg' in n or 'heladera' in n for n in names))
