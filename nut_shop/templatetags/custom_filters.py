from django import template
from django.utils.safestring import mark_safe
from django.shortcuts import get_object_or_404
from nut_shop.models import ProductVariant
import re

register = template.Library()

@register.filter(name='custom_format')
def custom_format(value):
    if not isinstance(value, str):
        return value

    # Обработка тегов <i>, <u>, <link>, <color>, <p>
    value = re.sub(r'<i>(.*?)</i>', r'<i>\1</i>', value)
    value = re.sub(r'<u>(.*?)</u>', r'<u>\1</u>', value)
    value = re.sub(r'<link="(.*?)">(.*?)</link>', r'<a href="\1" target="_blank">\2</a>', value)
    value = re.sub(r'<color="(#[0-9A-Fa-f]{6})">(.*?)</color>', r'<span style="color: \1">\2</span>', value)
    value = re.sub(r'<p>(.*?)</p>', r'<p style="font-size: 2em">\1</p>', value)
    
    # Обработка тега <image>
    def image_replace(match):
        url = match.group(1)
        return f'<img src="{url}" style="max-width: 200px; max-height: 300px; width: auto; height: auto;">'
    
    value = re.sub(r'<image>(.*?)</image>', image_replace, value)
    
    return mark_safe(value)

@register.filter(name='plain_text')
def plain_text(value):
    if not isinstance(value, str):
        return value
    
    # Удаляем все кастомные теги
    value = re.sub(r'<i>(.*?)</i>', r'\1', value)
    value = re.sub(r'<u>(.*?)</u>', r'\1', value)
    value = re.sub(r'<link="(.*?)">(.*?)</link>', r'\2', value)
    value = re.sub(r'<color="(#[0-9A-Fa-f]{6})">(.*?)</color>', r'\2', value)
    value = re.sub(r'<p>(.*?)</p>', r'\1', value)
    value = re.sub(r'<image>.*?</image>', '', value)
    
    return value

@register.filter(name='get_variant')
def get_variant(variant_id):
    return get_object_or_404(ProductVariant, id=variant_id)
