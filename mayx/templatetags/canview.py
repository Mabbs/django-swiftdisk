from django import template
from django.template.defaultfilters import stringfilter
register = template.Library()

@register.filter
@stringfilter
def canview(value):
    if value.split("/")[0] in ["image", "audio", "video", "text"]:
        return True
    return False
