"""
Tests para la funcionalidad de autenticación.
Incluye registro, login, logout y gestión de perfiles.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from api.models import Profile


class AuthenticationTestCase(TestCase):
    """Tests para autenticación de usuarios"""
    
    def setUp(self):
        """Configuración inicial para cada test"""
        self.client = APIClient()
        
        # Crear un usuario de prueba
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Crear un admin de prueba
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_superuser=True
        )
        self.admin_user.profile.role = Profile.Role.ADMIN
        self.admin_user.profile.save()
    
    def test_register_new_user(self):
        """Test: Registrar un nuevo usuario"""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post('/api/register/', data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertIn('user_id', response.data)
        self.assertEqual(response.data['username'], 'newuser')
        
        # Verificar que el usuario fue creado
        user = User.objects.get(username='newuser')
        self.assertEqual(user.email, 'newuser@example.com')
        
        # Verificar que el perfil fue creado con rol CLIENT
        self.assertEqual(user.profile.role, Profile.Role.CLIENT)
    
    def test_register_duplicate_username(self):
        """Test: No permitir registrar username duplicado"""
        data = {
            'username': 'testuser',  # Ya existe
            'email': 'another@example.com',
            'password': 'pass123'
        }
        
        response = self.client.post('/api/register/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_with_username(self):
        """Test: Login con username"""
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        response = self.client.post('/api/login/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['username'], 'testuser')
    
    def test_login_with_email(self):
        """Test: Login con email"""
        data = {
            'username': 'test@example.com',  # Usar email en lugar de username
            'password': 'testpass123'
        }
        
        response = self.client.post('/api/login/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['username'], 'testuser')
    
    def test_login_invalid_credentials(self):
        """Test: Login con credenciales inválidas"""
        data = {
            'username': 'testuser',
            'password': 'wrongpassword'
        }
        
        response = self.client.post('/api/login/', data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_logout(self):
        """Test: Cerrar sesión"""
        # Primero hacer login
        login_data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        login_response = self.client.post('/api/login/', login_data)
        token = login_response.data['token']
        
        # Configurar el cliente con el token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        
        # Hacer logout
        response = self.client.post('/api/logout/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verificar que el token fue eliminado (Django REST Framework devuelve 403)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        profile_response = self.client.get('/api/profile/')
        self.assertIn(profile_response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
    
    def test_get_user_profile(self):
        """Test: Obtener perfil de usuario autenticado"""
        # Login
        login_data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        login_response = self.client.post('/api/login/', login_data)
        token = login_response.data['token']
        
        # Obtener perfil
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.get('/api/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['email'], 'test@example.com')
        self.assertEqual(response.data['profile']['role'], Profile.Role.CLIENT)
    
    def test_update_user_profile(self):
        """Test: Actualizar perfil de usuario"""
        # Login
        login_data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        login_response = self.client.post('/api/login/', login_data)
        token = login_response.data['token']
        
        # Actualizar perfil
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        update_data = {
            'username': 'updateduser',
            'email': 'updated@example.com'
        }
        response = self.client.put('/api/profile/', update_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar cambios
        user = User.objects.get(id=self.test_user.id)
        self.assertEqual(user.username, 'updateduser')
        self.assertEqual(user.email, 'updated@example.com')
    
    def test_profile_requires_authentication(self):
        """Test: Perfil requiere autenticación"""
        response = self.client.get('/api/profile/')
        # Django REST Framework puede devolver 401 o 403
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class UserManagementTestCase(TestCase):
    """Tests para gestión de usuarios (solo admins)"""
    
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
        
        # Login como admin
        login_response = self.client.post('/api/login/', {
            'username': 'admin',
            'password': 'adminpass123'
        })
        self.admin_token = login_response.data['token']
    
    def test_admin_can_list_users(self):
        """Test: Admin puede listar usuarios"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token}')
        response = self.client.get('/api/users/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)  # Al menos admin y client
    
    def test_admin_can_create_user(self):
        """Test: Admin puede crear usuarios"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token}')
        
        data = {
            'username': 'newclient',
            'email': 'newclient@example.com',
            'password': 'pass123',
            'first_name': 'New',
            'last_name': 'Client',
            'profile': {
                'role': Profile.Role.CLIENT
            }
        }
        
        response = self.client.post('/api/users/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verificar que el usuario fue creado
        user = User.objects.get(username='newclient')
        self.assertEqual(user.email, 'newclient@example.com')
        self.assertEqual(user.profile.role, Profile.Role.CLIENT)
    
    def test_admin_can_update_user(self):
        """Test: Admin puede actualizar usuarios"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token}')
        
        data = {
            'email': 'updated_client@example.com',
            'profile': {
                'role': Profile.Role.CLIENT
            }
        }
        
        response = self.client.patch(f'/api/users/{self.client_user.id}/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar cambios
        user = User.objects.get(id=self.client_user.id)
        self.assertEqual(user.email, 'updated_client@example.com')
    
    def test_admin_can_delete_user(self):
        """Test: Admin puede eliminar usuarios (excepto a sí mismo)"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token}')
        
        response = self.client.delete(f'/api/users/{self.client_user.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verificar que fue eliminado
        self.assertFalse(User.objects.filter(id=self.client_user.id).exists())
    
    def test_admin_cannot_delete_self(self):
        """Test: Admin no puede eliminarse a sí mismo"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token}')
        
        response = self.client.delete(f'/api/users/{self.admin_user.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_client_cannot_access_user_management(self):
        """Test: Cliente no puede acceder a gestión de usuarios"""
        # Login como cliente
        login_response = self.client.post('/api/login/', {
            'username': 'client',
            'password': 'clientpass123'
        })
        client_token = login_response.data['token']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {client_token}')
        response = self.client.get('/api/users/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_admin_can_list_clients_only(self):
        """Test: Admin puede listar solo clientes"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token}')
        response = self.client.get('/api/clients/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar que todos son clientes
        for user_data in response.data:
            self.assertEqual(user_data['profile']['role'], Profile.Role.CLIENT)
