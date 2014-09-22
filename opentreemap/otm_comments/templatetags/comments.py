from django import template

register = template.Library()


@register.filter
def is_flagged_by(comment, user):
    return comment.is_flagged_by_user(user)
