# api/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('role',)


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()
    is_staff = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'profile', 'is_staff', 'is_superuser')


class RegisterSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(style={'input_type': 'password'}, write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password', 'password2')
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if data['password'] != data.get('password2'):
            raise serializers.ValidationError("Passwords must match.")
        return data

    def create(self, validated_data):
        validated_data.pop('password2', None)  # Elimina password2 para que no llegue al modelo User
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user


class AdminUserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'password', 'profile')
        # Hacemos que el email sea requerido al crear
        extra_kwargs = {'email': {'required': True}}

    # --- MÉTODO create AÑADIDO ---
    def create(self, validated_data):
        profile_data = validated_data.pop('profile')
        # Usamos create_user para hashear la contraseña correctamente
        user = User.objects.create_user(**validated_data)

        # Asignamos el rol del perfil
        Profile.objects.filter(user=user).update(**profile_data)

        return user

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)
        password = validated_data.pop('password', None)

        if profile_data:
            profile_serializer = self.fields['profile']
            profile_instance = instance.profile
            profile_serializer.update(profile_instance, profile_data)

        super().update(instance, validated_data)

        if password:
            instance.set_password(password)
            instance.save()

        return instance

class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializador para solicitar el reseteo de contraseña.
    Valida que se envíe un email.
    """
    email = serializers.EmailField(required=True)

class SetNewPasswordSerializer(serializers.Serializer):
    """
    Serializador para confirmar el reseteo con la nueva contraseña.
    """
    password = serializers.CharField(write_only=True, required=True)
    token = serializers.CharField(write_only=True, required=True)
    uidb64 = serializers.CharField(write_only=True, required=True)


# api/serializers.py
# ... (debajo de las otras clases de serializadores)

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializador para que un usuario actualice su propio perfil.
    Solo permite actualizar username, email y una nueva contraseña (opcional).
    """
    email = serializers.EmailField(required=False)
    # La contraseña es opcional y solo de escritura
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        # Definimos los únicos campos permitidos para la actualización
        fields = ('username', 'email', 'password')
        extra_kwargs = {
            'username': {'required': False},
        }

    def validate_username(self, value):
        # Valida que el nuevo username no esté en uso por otro usuario.
        if self.instance and User.objects.exclude(pk=self.instance.pk).filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        # Valida que el nuevo email no esté en uso por otro usuario.
        if self.instance and User.objects.exclude(pk=self.instance.pk).filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def update(self, instance, validated_data):
        # Actualiza el username y email si se proporcionaron
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)

        # Si el usuario envió una nueva contraseña, la hasheamos de forma segura
        password = validated_data.get('password', None)
        if password:
            instance.set_password(password)

        instance.save()
        return instance