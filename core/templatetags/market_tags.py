from django import template

register = template.Library()


@register.simple_tag
def multiply(a, b):
    try:
        return float(a) * float(b)
    except (ValueError, TypeError):
        return 0


@register.simple_tag
def subtract(a, b):
    try:
        return float(a) - float(b)
    except (ValueError, TypeError):
        return 0


@register.simple_tag
def add(a, b):
    try:
        return float(a) + float(b)
    except (ValueError, TypeError):
        return 0


@register.simple_tag
def divide(a, b):
    try:
        b = float(b)
        if b == 0:
            return 0
        return float(a) / b
    except (ValueError, TypeError):
        return 0


@register.filter
def currency(value):
    try:
        return f"\u20b1{float(value):,.2f}"
    except (ValueError, TypeError):
        return "\u20b10.00"


@register.filter
def percentage(value):
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return "0.00%"


@register.filter
def split(value, delimiter=','):
    """Split a string by delimiter and return a list."""
    return [item.strip() for item in value.split(delimiter) if item.strip()]


@register.filter
def textlines(value):
    """Split stored multi-line text (e.g. contract terms) into non-empty lines."""
    return [line.strip() for line in (value or '').splitlines() if line.strip()]


@register.filter
def badge(status):
    """Map a status string to the Emerald Glass badge classes."""
    palette = {
        'paid': 'badge badge-success',
        'unpaid': 'badge badge-danger',
        'overdue': 'badge badge-danger',
        'partial': 'badge badge-warning',
        'active': 'badge badge-success',
        'inactive': 'badge badge-muted',
        'suspended': 'badge badge-warning',
        'terminated': 'badge badge-danger',
        'vacant': 'badge badge-muted',
        'occupied': 'badge badge-success',
        'reserved': 'badge badge-warning',
        'maintenance': 'badge badge-warning',
        'void': 'badge badge-muted',
        'cancelled': 'badge badge-muted',
        'pending': 'badge badge-info',
        'expired': 'badge badge-warning',
        'payment reminder': 'badge badge-info',
        'overdue notice': 'badge badge-danger',
        'final demand': 'badge badge-danger',
        'vacancy notice': 'badge badge-info',
    }
    key = (status or '').lower()
    css_class = palette.get(key, 'badge badge-muted')
    return css_class
