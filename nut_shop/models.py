from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg, Min
from math import ceil
from django.utils.safestring import mark_safe
import re

class Category(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    formatted_description = models.TextField(blank=True, help_text="Используйте теги <i>, <u>, <link>, <color>, <p>, <image> для форматирования")

    def __str__(self):
        return self.name

    @property
    def main_image(self):
        return self.images.first()

    @property
    def average_rating(self):
        avg = self.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        return ceil(avg)

    def get_cheapest_variant(self):
        return self.variants.order_by('price').first()

    def video_preview(self, match):
        video_url = match.group(1)
        
        # YouTube
        youtube_match = re.search(r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]+)', video_url)
        if youtube_match:
            video_id = youtube_match.group(1)
            return f'''
            <div class="video-container">
                <iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
            </div>
            '''
        
        # Vimeo
        vimeo_match = re.search(r'vimeo\.com\/(\d+)', video_url)
        if vimeo_match:
            video_id = vimeo_match.group(1)
            return f'''
            <div class="video-container">
                <iframe src="https://player.vimeo.com/video/{video_id}" width="560" height="315" frameborder="0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>
            </div>
            '''
        
        # Другие видео (используем HTML5 video player)
        return f'''
        <div class="video-container">
            <video width="560" height="315" controls>
                <source src="{video_url}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </div>
        '''

    def formatted_description(self):
        desc = self.description
        # Обработка тега <b>
        desc = re.sub(r'<b>(.*?)</b>', r'<strong>\1</strong>', desc)
        # Обработка тега <vid>
        desc = re.sub(r'<vid>(.*?)</vid>', self.video_preview, desc)
        return mark_safe(desc)

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Image {self.order} for {self.product.name}"

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    weight = models.IntegerField(help_text="Вес в граммах")
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.weight}г"

    @property
    def price_per_kg(self):
        return self.price / self.weight if self.weight else 0

class PaymentMethod(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    shop_id = models.CharField(max_length=100, blank=True, null=True)
    secret_key = models.CharField(max_length=100, blank=True, null=True)
    bank_account = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return self.name
    
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending_payment', 'Ожидает оплаты'),
        ('processing', 'Подготовка'),
        ('shipped', 'Отправлено'),
        ('delivered', 'Доставлено'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True)
    full_name = models.CharField(max_length=200)
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Заказ {self.id} - {self.user.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='orderitems')
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product_variant.product.name} - {self.quantity} шт."

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def __str__(self):
        return self.user.username

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Отзыв на {self.product.name} от {self.user.username}"

class SiteSettings(models.Model):
    logo = models.ImageField(upload_to='logo/', null=True, blank=True)

    class Meta:
        verbose_name = 'Настройки сайта'
        verbose_name_plural = 'Настройки сайта'

    def __str__(self):
        return 'Настройки сайта'

    @classmethod
    def get_logo(cls):
        settings = cls.objects.first()
        if settings and settings.logo:
            return settings.logo.url
        return None
