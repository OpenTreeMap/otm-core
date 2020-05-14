from django.template.loader import render_to_string
from django.conf import settings
from django.core.mail import send_mail


def _get_email_subj_and_body(tmpl, ctxt):
    subject = render_to_string(
        'manage_treemap/emails/%s.subj.txt' % tmpl, ctxt)
    subject = ''.join(subject.splitlines())

    message = render_to_string(
        'manage_treemap/emails/%s.plaintext.txt' % tmpl, ctxt)

    html_message = render_to_string(
        'manage_treemap/emails/%s.body.txt' % tmpl, ctxt)

    return subject, message, html_message


def send_email(tmpl, ctxt, recipient_list):
    from_email = settings.DEFAULT_FROM_EMAIL
    subject, message, html_message = _get_email_subj_and_body(tmpl, ctxt)

    return send_mail(
        subject,
        message,
        '"Sustainable JC Green Team" <info@sustainablejc.org>',
        recipient_list,
        fail_silently=False,
        html_message=html_message
    )
