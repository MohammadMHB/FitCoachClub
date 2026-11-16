from django import template

register = template.Library()


@register.filter
def get_item(d, key):
    """دسترسی به مقدار دیکشنری با کلید دینامیک داخل تمپلیت."""
    if not d:
        return ''
    return d.get(key, '')
