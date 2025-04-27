from .models import Category, SiteSettings

def categories_and_settings(request):
    return {
        'categories': Category.objects.all(),
        'logo_url': SiteSettings.get_logo()
    }
