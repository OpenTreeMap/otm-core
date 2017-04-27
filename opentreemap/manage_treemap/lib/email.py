from django.core.mail import get_connection, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


def _get_email_subj_and_body(tmpl, ctxt):
    subject = render_to_string(
        'manage_treemap/emails/%s.subj.txt' % tmpl, ctxt)
    subject = ''.join(subject.splitlines())

    message = render_to_string(
        'manage_treemap/emails/%s.body.txt' % tmpl, ctxt)

    return subject, message


def send_email(tmpl, ctxt, recipient_list):
    from_email = settings.DEFAULT_FROM_EMAIL
    subject, message = _get_email_subj_and_body(tmpl, ctxt)

    connection = get_connection(fail_silently=True)
    mail = EmailMultiAlternatives(subject, message,
                                  from_email, recipient_list,
                                  connection=connection)

    mail.attach_alternative(message, 'text/html')

    return mail.send()
