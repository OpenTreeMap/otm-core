from django.utils.timezone import now


def default_handler(event):
    event.handled_at = now()
    event.handler_succeeded = True
    event.handler_log = 'No handler assigned'
    event.save()
    return event
