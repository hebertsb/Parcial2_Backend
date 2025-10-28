# notifications/firebase_service.py
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from typing import List, Dict, Optional
import logging
import os

logger = logging.getLogger(__name__)


class FirebaseService:
    """
    Servicio para manejar Firebase Cloud Messaging (FCM).
    Singleton para inicializar Firebase una sola vez.
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.initialize_firebase()
            self.__class__._initialized = True

    def initialize_firebase(self):
        """
        Inicializa la app de Firebase Admin SDK.
        Requiere el archivo de credenciales de Firebase en la ruta especificada.
        """
        try:
            # Verificar si ya está inicializado
            if firebase_admin._apps:
                logger.info("Firebase Admin SDK ya está inicializado")
                return

            # Ruta del archivo de credenciales
            cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
            
            if not cred_path:
                logger.warning(
                    "FIREBASE_CREDENTIALS_PATH no configurado en settings. "
                    "Las notificaciones push no funcionarán hasta configurarlo."
                )
                return
            
            if not os.path.exists(cred_path):
                logger.warning(
                    f"Archivo de credenciales de Firebase no encontrado en: {cred_path}. "
                    "Las notificaciones push no funcionarán hasta configurarlo."
                )
                return

            # Inicializar Firebase
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error al inicializar Firebase Admin SDK: {str(e)}")

    def is_initialized(self) -> bool:
        """Verifica si Firebase está inicializado correctamente"""
        return bool(firebase_admin._apps)

    def send_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict] = None,
        image_url: Optional[str] = None
    ) -> Optional[str]:
        """
        Envía una notificación push a un dispositivo específico.
        
        Args:
            token: Token FCM del dispositivo
            title: Título de la notificación
            body: Cuerpo del mensaje
            data: Datos adicionales (opcional)
            image_url: URL de imagen para la notificación (opcional)
            
        Returns:
            message_id si se envió correctamente, None si falló
        """
        if not self.is_initialized():
            logger.warning("Firebase no está inicializado. No se puede enviar la notificación.")
            return None

        try:
            # Preparar el mensaje
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url if image_url else None
            )

            # Preparar datos adicionales
            message_data = data if data else {}
            
            # Asegurar que todos los valores en data sean strings
            message_data = {k: str(v) for k, v in message_data.items()}

            # Crear el mensaje
            message = messaging.Message(
                notification=notification,
                data=message_data,
                token=token,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        icon='ic_notification',
                        color='#007AFF',
                        sound='default',
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            badge=1,
                            sound='default',
                        )
                    )
                ),
                webpush=messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(
                        icon='/static/icon.png',
                        badge='/static/badge.png',
                    )
                )
            )

            # Enviar el mensaje
            response = messaging.send(message)
            logger.info(f"Notificación enviada exitosamente. ID: {response}")
            return response

        except messaging.UnregisteredError:
            logger.warning(f"Token no registrado: {token}")
            return None
        except Exception as e:
            logger.error(f"Error al enviar notificación: {str(e)}")
            return None

    def send_multicast_notification(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict] = None,
        image_url: Optional[str] = None
    ) -> Dict:
        """
        Envía una notificación a múltiples dispositivos.
        
        Args:
            tokens: Lista de tokens FCM
            title: Título de la notificación
            body: Cuerpo del mensaje
            data: Datos adicionales (opcional)
            image_url: URL de imagen (opcional)
            
        Returns:
            Dict con success_count, failure_count y tokens_to_remove
        """
        if not self.is_initialized():
            logger.warning("Firebase no está inicializado. No se pueden enviar notificaciones.")
            return {'success_count': 0, 'failure_count': len(tokens), 'tokens_to_remove': []}

        if not tokens:
            logger.warning("No se proporcionaron tokens para enviar notificaciones")
            return {'success_count': 0, 'failure_count': 0, 'tokens_to_remove': []}

        try:
            # Preparar datos
            message_data = data if data else {}
            message_data = {k: str(v) for k, v in message_data.items()}

            # Crear mensaje multicast
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                    image=image_url if image_url else None
                ),
                data=message_data,
                tokens=tokens,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        icon='ic_notification',
                        color='#007AFF',
                        sound='default',
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            badge=1,
                            sound='default',
                        )
                    )
                ),
            )

            # Enviar mensaje
            response = messaging.send_multicast(message)
            
            # Identificar tokens inválidos
            tokens_to_remove = []
            if response.failure_count > 0:
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        # Token inválido o no registrado
                        if isinstance(resp.exception, (messaging.UnregisteredError, 
                                                      messaging.SenderIdMismatchError)):
                            tokens_to_remove.append(tokens[idx])
                        logger.warning(f"Error enviando a token {idx}: {resp.exception}")

            logger.info(
                f"Notificación multicast enviada. "
                f"Exitosos: {response.success_count}, "
                f"Fallidos: {response.failure_count}"
            )

            return {
                'success_count': response.success_count,
                'failure_count': response.failure_count,
                'tokens_to_remove': tokens_to_remove
            }

        except Exception as e:
            logger.error(f"Error al enviar notificación multicast: {str(e)}")
            return {
                'success_count': 0,
                'failure_count': len(tokens),
                'tokens_to_remove': []
            }

    def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Envía una notificación a un topic (tema).
        Útil para notificaciones broadcast a grupos de usuarios.
        
        Args:
            topic: Nombre del topic
            title: Título de la notificación
            body: Cuerpo del mensaje
            data: Datos adicionales (opcional)
            
        Returns:
            message_id si se envió correctamente, None si falló
        """
        if not self.is_initialized():
            logger.warning("Firebase no está inicializado.")
            return None

        try:
            message_data = data if data else {}
            message_data = {k: str(v) for k, v in message_data.items()}

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=message_data,
                topic=topic
            )

            response = messaging.send(message)
            logger.info(f"Notificación enviada al topic '{topic}'. ID: {response}")
            return response

        except Exception as e:
            logger.error(f"Error al enviar notificación al topic: {str(e)}")
            return None

    def subscribe_to_topic(self, tokens: List[str], topic: str) -> Dict:
        """Suscribe tokens a un topic"""
        if not self.is_initialized():
            return {'success_count': 0, 'failure_count': len(tokens)}

        try:
            response = messaging.subscribe_to_topic(tokens, topic)
            logger.info(f"Suscripción al topic '{topic}': {response.success_count} exitosos")
            return {
                'success_count': response.success_count,
                'failure_count': response.failure_count
            }
        except Exception as e:
            logger.error(f"Error al suscribir al topic: {str(e)}")
            return {'success_count': 0, 'failure_count': len(tokens)}

    def unsubscribe_from_topic(self, tokens: List[str], topic: str) -> Dict:
        """Desuscribe tokens de un topic"""
        if not self.is_initialized():
            return {'success_count': 0, 'failure_count': len(tokens)}

        try:
            response = messaging.unsubscribe_from_topic(tokens, topic)
            logger.info(f"Desuscripción del topic '{topic}': {response.success_count} exitosos")
            return {
                'success_count': response.success_count,
                'failure_count': response.failure_count
            }
        except Exception as e:
            logger.error(f"Error al desuscribir del topic: {str(e)}")
            return {'success_count': 0, 'failure_count': len(tokens)}


# Instancia singleton del servicio
firebase_service = FirebaseService()
