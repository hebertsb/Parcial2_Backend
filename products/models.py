from django.db import models
from django.core.exceptions import ValidationError
import os


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, help_text="Unique URL-friendly name for the category")

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name
    
    def clean(self):
        """Validaciones personalizadas"""
        if not self.name or not self.name.strip():
            raise ValidationError({'name': 'El nombre de la categoría no puede estar vacío.'})
        
        # Asegurar que el slug no tenga espacios
        if self.slug and ' ' in self.slug:
            raise ValidationError({'slug': 'El slug no puede contener espacios.'})


class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    # Campos de fecha automáticos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at'] # Muestra los productos más nuevos primero

    def __str__(self):
        return self.name
    
    def clean(self):
        """Validaciones personalizadas"""
        errors = {}
        
        # Validar precio
        if self.price is not None and self.price <= 0:
            errors['price'] = 'El precio debe ser mayor a 0.'
        
        # Validar nombre
        if not self.name or not self.name.strip():
            errors['name'] = 'El nombre del producto no puede estar vacío.'
        
        # Validar stock (aunque sea PositiveIntegerField, por si acaso)
        if self.stock < 0:
            errors['stock'] = 'El stock no puede ser negativo.'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Override save para ejecutar validaciones"""
        self.full_clean()  # Ejecuta clean() y otras validaciones
        super().save(*args, **kwargs)
    
    @property
    def is_available(self):
        """Verifica si el producto está disponible"""
        return self.stock > 0
    
    @property
    def is_low_stock(self):
        """Verifica si el producto tiene stock bajo (menos de 10)"""
        return 0 < self.stock < 10
    
    @property
    def image_url(self):
        """
        Devuelve la URL de la imagen si existe, None si no existe o está rota
        """
        if self.image:
            # Verificar si el archivo existe físicamente
            try:
                if os.path.isfile(self.image.path):
                    return self.image.url
            except (ValueError, AttributeError):
                pass
        return None
    
    @property
    def has_valid_image(self):
        """Verifica si el producto tiene una imagen válida"""
        return self.image_url is not None
    
    def delete_image(self):
        """Elimina la imagen física del producto"""
        if self.image:
            try:
                if os.path.isfile(self.image.path):
                    os.remove(self.image.path)
                self.image = None
                self.save()
                return True
            except Exception:
                pass
        return False