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
def badge(status):
    palette = {
        'paid': 'bg-green-100 text-green-800',
        'unpaid': 'bg-yellow-100 text-yellow-800',
        'overdue': 'bg-red-100 text-red-800',
        'partial': 'bg-orange-100 text-orange-800',
        'active': 'bg-green-100 text-green-800',
        'inactive': 'bg-gray-100 text-gray-800',
        'suspended': 'bg-red-100 text-red-800',
        'terminated': 'bg-red-100 text-red-800',
        'vacant': 'bg-blue-100 text-blue-800',
        'occupied': 'bg-green-100 text-green-800',
        'reserved': 'bg-purple-100 text-purple-800',
        'maintenance': 'bg-orange-100 text-orange-800',
        'void': 'bg-gray-100 text-gray-800',
        'cancelled': 'bg-red-100 text-red-800',
        'pending': 'bg-yellow-100 text-yellow-800',
        'expired': 'bg-gray-100 text-gray-800',
        'payment reminder': 'bg-blue-100 text-blue-800',
        'overdue notice': 'bg-red-100 text-red-800',
        'final demand': 'bg-red-100 text-red-800',
        'vacancy notice': 'bg-blue-100 text-blue-800',
    }
    key = (status or '').lower()
    css_class = palette.get(key, 'bg-gray-100 text-gray-800')
    return css_class
