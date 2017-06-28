from django.template import Library

register = Library()


@register.filter
def in_thread_order(comments):
    '''Convert a list of comments in chronological order into a list of
    comments in tree order, where the children of a comment appear
    directly after the comment in the list.'''
    roots = []
    children_of = {}
    for c in comments:
        if c.parent:
            if c.parent.id not in children_of:
                children_of[c.parent.id] = []
            children_of[c.parent.id].append(c)
        else:
            roots.append(c)

    def order_children_for(parent):
        if parent.id in children_of:
            children = []
            for child in children_of[parent.id]:
                children.append(child)
                children.extend(order_children_for(child))
            return children
        else:
            return []

    sequenced = []
    for root in roots:
        sequenced.append(root)
        sequenced.extend(order_children_for(root))

    return sequenced
