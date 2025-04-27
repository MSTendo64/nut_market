from django.apps import AppConfig
from django.contrib.admin.apps import AdminConfig
from django.contrib import admin

class NutShopAdminSite(admin.AdminSite):
    site_header = 'Орех Маркет Администрирование'
    site_title = 'Орех Маркет'
    index_title = 'Панель управления'

class NutShopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nut_shop'

    def ready(self):
        import nut_shop.templatetags.custom_filters

class NutShopAdminConfig(AdminConfig):
    default_site = 'nut_shop.apps.NutShopAdminSite'
