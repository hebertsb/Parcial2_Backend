# notifications/tests.py
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from .models import DeviceToken, Notification, NotificationPreference
from .notification_service import NotificationService


class DeviceTokenModelTest(TestCase):
    """Tests para el modelo DeviceToken"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_create_device_token(self):
        """Test crear token de dispositivo"""
        token = DeviceToken.objects.create(
            user=self.user,
            token='test_fcm_token',
            platform=DeviceToken.Platform.ANDROID,
            device_name='Test Device'
        )
        self.assertEqual(token.user, self.user)
        self.assertTrue(token.is_active)
        self.assertEqual(token.platform, 'ANDROID')

    def test_device_token_str(self):
        """Test representación en string"""
        token = DeviceToken.objects.create(
            user=self.user,
            token='test_token',
            platform=DeviceToken.Platform.WEB
        )
        self.assertIn(self.user.username, str(token))


class NotificationModelTest(TestCase):
    """Tests para el modelo Notification"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_create_notification(self):
        """Test crear notificación"""
        notification = Notification.objects.create(
            user=self.user,
            title='Test Notification',
            body='Test Body',
            notification_type=Notification.NotificationType.SYSTEM
        )
        self.assertEqual(notification.status, Notification.Status.PENDING)
        self.assertIsNone(notification.sent_at)

    def test_mark_as_sent(self):
        """Test marcar notificación como enviada"""
        notification = Notification.objects.create(
            user=self.user,
            title='Test',
            body='Body'
        )
        notification.mark_as_sent('test_message_id')
        self.assertEqual(notification.status, Notification.Status.SENT)
        self.assertIsNotNone(notification.sent_at)
        self.assertEqual(notification.fcm_message_id, 'test_message_id')

    def test_mark_as_read(self):
        """Test marcar notificación como leída"""
        notification = Notification.objects.create(
            user=self.user,
            title='Test',
            body='Body'
        )
        notification.mark_as_sent()
        notification.mark_as_read()
        self.assertEqual(notification.status, Notification.Status.READ)
        self.assertIsNotNone(notification.read_at)


class NotificationPreferenceModelTest(TestCase):
    """Tests para el modelo NotificationPreference"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_create_preferences(self):
        """Test crear preferencias"""
        prefs = NotificationPreference.objects.create(user=self.user)
        self.assertTrue(prefs.enabled)
        self.assertTrue(prefs.sale_notifications)
        self.assertTrue(prefs.product_notifications)

    def test_should_send_notification(self):
        """Test verificar si se debe enviar notificación"""
        prefs = NotificationPreference.objects.create(
            user=self.user,
            sale_notifications=False
        )
        self.assertFalse(prefs.should_send_notification('SALE_CREATED'))
        self.assertTrue(prefs.should_send_notification('PRODUCT_CREATED'))


class NotificationServiceTest(TestCase):
    """Tests para NotificationService"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='adminpass123',
            email='admin@test.com'
        )

    def test_register_device_token(self):
        """Test registrar token de dispositivo"""
        token = NotificationService.register_device_token(
            user=self.user,
            token='test_token_123',
            platform='ANDROID',
            device_name='Test Device'
        )
        self.assertEqual(token.user, self.user)
        self.assertEqual(token.token, 'test_token_123')
        self.assertTrue(token.is_active)

    def test_unregister_device_token(self):
        """Test desregistrar token"""
        token = NotificationService.register_device_token(
            user=self.user,
            token='test_token_123'
        )
        success = NotificationService.unregister_device_token('test_token_123')
        self.assertTrue(success)
        token.refresh_from_db()
        self.assertFalse(token.is_active)

    def test_get_unread_count(self):
        """Test obtener cuenta de no leídas"""
        Notification.objects.create(
            user=self.user,
            title='Test 1',
            body='Body 1',
            status=Notification.Status.SENT
        )
        Notification.objects.create(
            user=self.user,
            title='Test 2',
            body='Body 2',
            status=Notification.Status.READ
        )
        count = NotificationService.get_unread_count(self.user)
        self.assertEqual(count, 1)


class NotificationAPITest(APITestCase):
    """Tests para la API de notificaciones"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='adminpass123',
            email='admin@test.com'
        )
        self.client = APIClient()

    def test_register_device_token_authenticated(self):
        """Test registrar token (autenticado)"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/notifications/device-tokens/register/', {
            'token': 'test_fcm_token',
            'platform': 'WEB',
            'device_name': 'Chrome Browser'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['token'], 'test_fcm_token')

    def test_register_device_token_unauthenticated(self):
        """Test registrar token (no autenticado) - debe fallar"""
        response = self.client.post('/api/notifications/device-tokens/register/', {
            'token': 'test_fcm_token',
            'platform': 'WEB'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_my_notifications(self):
        """Test obtener mis notificaciones"""
        self.client.force_authenticate(user=self.user)
        
        # Crear notificaciones
        Notification.objects.create(
            user=self.user,
            title='Test Notification',
            body='Test Body'
        )
        
        response = self.client.get('/api/notifications/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_unread_count(self):
        """Test obtener cuenta de no leídas"""
        self.client.force_authenticate(user=self.user)
        
        Notification.objects.create(
            user=self.user,
            title='Test',
            body='Body',
            status=Notification.Status.SENT
        )
        
        response = self.client.get('/api/notifications/notifications/unread_count/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_mark_notification_as_read(self):
        """Test marcar notificación como leída"""
        self.client.force_authenticate(user=self.user)
        
        notification = Notification.objects.create(
            user=self.user,
            title='Test',
            body='Body',
            status=Notification.Status.SENT
        )
        
        response = self.client.post(
            f'/api/notifications/notifications/{notification.id}/mark_as_read/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertEqual(notification.status, Notification.Status.READ)

    def test_get_preferences(self):
        """Test obtener preferencias"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get('/api/notifications/preferences/my_preferences/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['enabled'])

    def test_update_preferences(self):
        """Test actualizar preferencias"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.patch('/api/notifications/preferences/update_preferences/', {
            'sale_notifications': False,
            'product_notifications': True
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['sale_notifications'])
        self.assertTrue(response.data['product_notifications'])
