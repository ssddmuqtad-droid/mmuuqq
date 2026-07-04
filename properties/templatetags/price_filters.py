from django import template

register = template.Library()


@register.filter
def format_price(value):
    """Format price with Iraqi Dinar currency"""
    if value is None:
        return '0 د.ع'
    try:
        # Format with thousands separator
        formatted = f"{int(value):,}"
        return f'{formatted} د.ع'
    except (ValueError, TypeError):
        return f'{value} د.ع'


@register.filter
def mul(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
