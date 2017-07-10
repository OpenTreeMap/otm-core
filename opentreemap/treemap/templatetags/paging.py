from django import template

register = template.Library()


@register.filter
def four_before_page(page_range, page):
    """Returns 4 or fewer pages before the given (1-based) page number"""
    return list(page_range)[max(page-5, 0):max(page-1, 0)]


@register.filter
def four_after_page(page_range, page):
    """Returns 4 or fewer pages after the given (1-based) page number"""
    return list(page_range)[page:min(page+4, len(page_range))]
