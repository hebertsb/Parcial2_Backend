# tests/test_audit_reports.py
"""
Tests completos para la funcionalidad de reportes de auditoría.
Verifica generación en JSON, PDF y Excel con filtros personalizados.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timedelta
from django.contrib.auth.models import User

from sales.models_audit import AuditLog, UserSession


class AuditReportGenerationTestCase(TestCase):
    """
    Tests para verificar la generación de reportes de auditoría.
    """

    def setUp(self):
        """
        Configuración inicial: crear usuarios y datos de prueba.
        """
        self.client = APIClient()

        # Crear usuarios
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='testpass123'
        )

        self.regular_user = User.objects.create_user(
            username='user_test',
            email='user@test.com',
            password='testpass123'
        )

        # Autenticar como admin
        self.client.force_authenticate(user=self.admin_user)

        # Crear logs de prueba con diferentes características
        now = timezone.now()

        # Logs exitosos
        for i in range(5):
            AuditLog.objects.create(
                username='admin_test',
                action_type='READ',
                action_description=f'Lectura de productos {i}',
                http_method='GET',
                endpoint='/api/products/',
                ip_address='192.168.1.100',
                response_status=200,
                success=True,
                severity='LOW',
                response_time_ms=50 + i * 10,
                timestamp=now - timedelta(minutes=i)
            )

        # Logs con errores
        for i in range(3):
            AuditLog.objects.create(
                username='user_test',
                action_type='AUTH',
                action_description=f'Intento de login fallido {i}',
                http_method='POST',
                endpoint='/api/auth/login/',
                ip_address='192.168.1.200',
                response_status=401,
                success=False,
                severity='HIGH',
                response_time_ms=100 + i * 10,
                timestamp=now - timedelta(hours=i)
            )

        # Logs de diferentes tipos
        AuditLog.objects.create(
            username='admin_test',
            action_type='CREATE',
            action_description='Creación de producto',
            http_method='POST',
            endpoint='/api/products/',
            ip_address='192.168.1.100',
            response_status=201,
            success=True,
            severity='MEDIUM',
            response_time_ms=150,
            timestamp=now - timedelta(days=1)
        )

        AuditLog.objects.create(
            username='admin_test',
            action_type='DELETE',
            action_description='Eliminación de producto',
            http_method='DELETE',
            endpoint='/api/products/5/',
            ip_address='192.168.1.100',
            response_status=204,
            success=True,
            severity='CRITICAL',
            response_time_ms=200,
            timestamp=now - timedelta(days=2)
        )

        # Crear sesiones de prueba
        session = UserSession.objects.create(
            user=self.admin_user,
            session_key='test_session_key_123',
            ip_address='192.168.1.100',
            user_agent='Test Browser',
            login_time=now - timedelta(hours=2),
            is_active=True
        )
        session.last_activity = now

        print(f"[OK] Datos de prueba creados: {AuditLog.objects.count()} logs")

    def test_generate_report_json_format(self):
        """
        Test 1: Generar reporte en formato JSON sin filtros.
        """
        print("\n[TEST 1] Generando reporte en formato JSON...")

        url = reverse('generate-audit-report')
        data = {
            'filters': {},
            'format': 'json'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['format'], 'json')
        self.assertIn('data', response.data)

        report_data = response.data['data']
        self.assertIn('title', report_data)
        self.assertIn('headers', report_data)
        self.assertIn('rows', report_data)
        self.assertIn('totals', report_data)

        # Verificar que hay datos
        self.assertGreater(len(report_data['rows']), 0)
        self.assertGreater(report_data['totals']['total_registros'], 0)

        print(f"[OK] Reporte JSON generado correctamente")
        print(f"  - Total de registros: {report_data['totals']['total_registros']}")
        print(f"  - Éxitos: {report_data['totals']['total_exitos']}")
        print(f"  - Errores: {report_data['totals']['total_errores']}")

    def test_generate_report_with_user_filter(self):
        """
        Test 2: Generar reporte filtrado por usuario específico.
        """
        print("\n[TEST 2] Generando reporte filtrado por usuario...")

        url = reverse('generate-audit-report')
        data = {
            'filters': {
                'user': 'admin_test'
            },
            'format': 'json'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report_data = response.data['data']

        # Verificar que todos los logs son del usuario solicitado
        for row in report_data['rows']:
            self.assertIn('admin_test', row[1])  # Columna de usuario

        print(f"[OK] Filtro por usuario funciona correctamente")
        print(f"  - Registros de admin_test: {len(report_data['rows'])}")

    def test_generate_report_with_action_type_filter(self):
        """
        Test 3: Generar reporte filtrado por tipo de acción.
        """
        print("\n[TEST 3] Generando reporte filtrado por tipo de acción...")

        url = reverse('generate-audit-report')
        data = {
            'filters': {
                'action_type': 'AUTH'
            },
            'format': 'json'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report_data = response.data['data']

        # Verificar que solo hay logs de tipo AUTH
        self.assertEqual(report_data['totals']['total_registros'], 3)

        print(f"[OK] Filtro por tipo de acción funciona correctamente")
        print(f"  - Registros AUTH: {report_data['totals']['total_registros']}")

    def test_generate_report_with_success_filter(self):
        """
        Test 4: Generar reporte solo de errores.
        """
        print("\n[TEST 4] Generando reporte solo de errores...")

        url = reverse('generate-audit-report')
        data = {
            'filters': {
                'success': False
            },
            'format': 'json'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report_data = response.data['data']

        # Verificar que solo hay errores
        self.assertEqual(report_data['totals']['total_errores'], report_data['totals']['total_registros'])

        print(f"[OK] Filtro por éxito/error funciona correctamente")
        print(f"  - Total de errores: {report_data['totals']['total_errores']}")

    def test_generate_report_with_date_range(self):
        """
        Test 5: Generar reporte con rango de fechas.
        """
        print("\n[TEST 5] Generando reporte con rango de fechas...")

        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        url = reverse('generate-audit-report')
        data = {
            'filters': {
                'start_date': yesterday,
                'end_date': today
            },
            'format': 'json'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report_data = response.data['data']

        # Verificar que se filtraron por fecha
        self.assertGreater(report_data['totals']['total_registros'], 0)

        print(f"[OK] Filtro por rango de fechas funciona correctamente")
        print(f"  - Registros en rango: {report_data['totals']['total_registros']}")

    def test_generate_report_with_severity_filter(self):
        """
        Test 6: Generar reporte filtrado por severidad.
        """
        print("\n[TEST 6] Generando reporte filtrado por severidad...")

        url = reverse('generate-audit-report')
        data = {
            'filters': {
                'severity': 'HIGH'
            },
            'format': 'json'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report_data = response.data['data']

        # Verificar que hay registros de severidad HIGH
        self.assertGreater(report_data['totals']['total_registros'], 0)

        print(f"[OK] Filtro por severidad funciona correctamente")
        print(f"  - Registros HIGH: {report_data['totals']['total_registros']}")

    def test_generate_report_with_multiple_filters(self):
        """
        Test 7: Generar reporte con múltiples filtros combinados.
        """
        print("\n[TEST 7] Generando reporte con múltiples filtros...")

        url = reverse('generate-audit-report')
        data = {
            'filters': {
                'user': 'user_test',
                'action_type': 'AUTH',
                'success': False
            },
            'format': 'json'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report_data = response.data['data']

        # Verificar que se aplicaron todos los filtros
        self.assertEqual(report_data['totals']['total_registros'], 3)
        self.assertEqual(report_data['totals']['total_errores'], 3)

        print(f"[OK] Filtros combinados funcionan correctamente")
        print(f"  - Registros que cumplen todos los filtros: {report_data['totals']['total_registros']}")

    def test_generate_report_pdf_format(self):
        """
        Test 8: Generar reporte en formato PDF.
        """
        print("\n[TEST 8] Generando reporte en formato PDF...")

        url = reverse('generate-audit-report')
        data = {
            'filters': {
                'user': 'admin_test'
            },
            'format': 'pdf'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('bitacora_auditoria.pdf', response['Content-Disposition'])

        # Verificar que el PDF tiene contenido
        self.assertGreater(len(response.content), 0)

        # Verificar que comienza con el header de PDF
        self.assertTrue(response.content.startswith(b'%PDF'))

        print(f"[OK] Reporte PDF generado correctamente")
        print(f"  - Tamaño del archivo: {len(response.content)} bytes")

    def test_generate_report_excel_format(self):
        """
        Test 9: Generar reporte en formato Excel.
        """
        print("\n[TEST 9] Generando reporte en formato Excel...")

        url = reverse('generate-audit-report')
        data = {
            'filters': {
                'action_type': 'READ'
            },
            'format': 'excel'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('bitacora_auditoria.xlsx', response['Content-Disposition'])

        # Verificar que el Excel tiene contenido
        self.assertGreater(len(response.content), 0)

        # Verificar que es un archivo ZIP (XLSX es un ZIP)
        self.assertTrue(response.content.startswith(b'PK'))

        print(f"[OK] Reporte Excel generado correctamente")
        print(f"  - Tamaño del archivo: {len(response.content)} bytes")

    def test_generate_session_report_json(self):
        """
        Test 10: Generar reporte de sesiones en formato JSON.
        """
        print("\n[TEST 10] Generando reporte de sesiones en JSON...")

        url = reverse('generate-session-report')
        data = {
            'filters': {},
            'format': 'json'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

        report_data = response.data['data']
        self.assertIn('title', report_data)
        self.assertIn('totals', report_data)
        self.assertGreater(report_data['totals']['total_sesiones'], 0)

        print(f"[OK] Reporte de sesiones JSON generado correctamente")
        print(f"  - Total sesiones: {report_data['totals']['total_sesiones']}")
        print(f"  - Activas: {report_data['totals']['sesiones_activas']}")

    def test_generate_session_report_pdf(self):
        """
        Test 11: Generar reporte de sesiones en formato PDF.
        """
        print("\n[TEST 11] Generando reporte de sesiones en PDF...")

        url = reverse('generate-session-report')
        data = {
            'filters': {
                'user': 'admin_test'
            },
            'format': 'pdf'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('sesiones_usuarios.pdf', response['Content-Disposition'])
        self.assertGreater(len(response.content), 0)

        print(f"[OK] Reporte de sesiones PDF generado correctamente")
        print(f"  - Tamaño: {len(response.content)} bytes")

    def test_generate_session_report_excel(self):
        """
        Test 12: Generar reporte de sesiones en formato Excel.
        """
        print("\n[TEST 12] Generando reporte de sesiones en Excel...")

        url = reverse('generate-session-report')
        data = {
            'filters': {},
            'format': 'excel'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertIn('sesiones_usuarios.xlsx', response['Content-Disposition'])
        self.assertGreater(len(response.content), 0)

        print(f"[OK] Reporte de sesiones Excel generado correctamente")
        print(f"  - Tamaño: {len(response.content)} bytes")

    def test_report_requires_admin_permission(self):
        """
        Test 13: Verificar que solo admins pueden generar reportes.
        """
        print("\n[TEST 13] Verificando permisos de administrador...")

        # Autenticar como usuario regular
        self.client.force_authenticate(user=self.regular_user)

        url = reverse('generate-audit-report')
        data = {
            'filters': {},
            'format': 'json'
        }

        response = self.client.post(url, data, format='json')

        # Debería ser 403 Forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        print(f"[OK] Control de permisos funciona correctamente")
        print(f"  - Usuario regular bloqueado: {response.status_code}")

    def test_report_metadata_included(self):
        """
        Test 14: Verificar que el reporte incluye metadata completa.
        """
        print("\n[TEST 14] Verificando metadata del reporte...")

        url = reverse('generate-audit-report')
        data = {
            'filters': {
                'user': 'admin_test',
                'action_type': 'READ'
            },
            'format': 'json'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report_data = response.data['data']

        # Verificar metadata
        self.assertIn('metadata', report_data)
        self.assertIn('generado_en', report_data['metadata'])
        self.assertIn('filtros_aplicados', report_data['metadata'])

        # Verificar summary
        self.assertIn('summary', report_data)
        self.assertIn('usuarios_unicos', report_data['summary'])
        self.assertIn('ips_unicas', report_data['summary'])

        print(f"[OK] Metadata completa incluida en el reporte")
        print(f"  - Usuarios únicos: {report_data['summary']['usuarios_unicos']}")
        print(f"  - IPs únicas: {report_data['summary']['ips_unicas']}")


class AuditReportContentTestCase(TestCase):
    """
    Tests para verificar el contenido y estructura de los reportes.
    """

    def setUp(self):
        """Configuración inicial."""
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.admin_user)

        # Crear algunos logs
        for i in range(3):
            AuditLog.objects.create(
                username='admin',
                action_type='READ',
                action_description=f'Test action {i}',
                http_method='GET',
                endpoint='/api/test/',
                ip_address='127.0.0.1',
                response_status=200,
                success=True,
                severity='LOW',
                response_time_ms=50
            )

    def test_report_headers_correct(self):
        """
        Test 15: Verificar que los headers del reporte son correctos.
        """
        print("\n[TEST 15] Verificando headers del reporte...")

        url = reverse('generate-audit-report')
        response = self.client.post(url, {'filters': {}, 'format': 'json'}, format='json')

        headers = response.data['data']['headers']
        expected_headers = [
            'Fecha/Hora',
            'Usuario',
            'Acción',
            'Endpoint',
            'IP',
            'Estado',
            'Tiempo (ms)',
            'Severidad'
        ]

        self.assertEqual(headers, expected_headers)
        print(f"[OK] Headers correctos: {len(headers)} columnas")

    def test_report_totals_calculation(self):
        """
        Test 16: Verificar que los totales se calculan correctamente.
        """
        print("\n[TEST 16] Verificando cálculo de totales...")

        url = reverse('generate-audit-report')
        response = self.client.post(url, {'filters': {}, 'format': 'json'}, format='json')

        totals = response.data['data']['totals']

        self.assertEqual(totals['total_registros'], 3)
        self.assertEqual(totals['total_exitos'], 3)
        self.assertEqual(totals['total_errores'], 0)
        self.assertEqual(totals['tasa_error'], '0.00%')

        print(f"[OK] Totales calculados correctamente")
        print(f"  - Total: {totals['total_registros']}")
        print(f"  - Tasa de error: {totals['tasa_error']}")


def run_all_tests():
    """
    Función helper para ejecutar todos los tests y mostrar un resumen.
    """
    print("\n" + "="*70)
    print("EJECUTANDO SUITE COMPLETA DE TESTS DE REPORTES DE AUDITORÍA")
    print("="*70)

    from django.test import TestRunner
    runner = TestRunner(verbosity=2)
    runner.run_tests(['tests.test_audit_reports'])

    print("\n" + "="*70)
    print("TESTS COMPLETADOS")
    print("="*70)


if __name__ == '__main__':
    run_all_tests()
