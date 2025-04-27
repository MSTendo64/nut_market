from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from nut_shop.views import custom_admin, custom_model_view, custom_model_add, custom_model_change
from nut_shop.admin import admin_site

urlpatterns = [
    path('root/', custom_admin, name='custom_admin'),
    path('root/<str:app_label>/<str:model_name>/', custom_model_view, name='custom_model_view'),
    path('root/<str:app_label>/<str:model_name>/add/', custom_model_add, name='custom_model_add'),
    path('root/<str:app_label>/<str:model_name>/<path:object_id>/change/', custom_model_change, name='custom_model_change'),
    path('admin/', admin_site.urls),  # Добавьте эту строку
    path('', include('nut_shop.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
