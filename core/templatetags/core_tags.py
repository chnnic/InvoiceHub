from django import template
from django.utils.translation import get_language
from decimal import Decimal, InvalidOperation
register=template.Library()
@register.filter
def attr(obj,name): return getattr(obj,name,"")
@register.filter
def money(value):
    try: formatted=f"{Decimal(value):,.0f}"
    except (InvalidOperation,TypeError,ValueError): return value
    return formatted.replace(",",".") if get_language()=="id" else formatted
