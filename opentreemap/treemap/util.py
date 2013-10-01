import json
import datetime
import Image
import hashlib
from collections import OrderedDict
from cStringIO import StringIO

from functools import wraps
from urlparse import urlparse
from django.template import RequestContext
from django.shortcuts import get_object_or_404, render_to_response, resolve_url
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseRedirect)
from django.views.decorators.http import require_http_methods
from django.utils.encoding import force_str, force_text
from django.utils.functional import Promise
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as trans
from django.core.files.uploadedfile import SimpleUploadedFile, File

from treemap.instance import Instance


def safe_get_model_class(model_string):
    """
    In a couple of cases we want to be able to convert a string
    into a valid django model class. For instance, if we have
    'Plot' we want to get the actual class for 'treemap.models.Plot'
    in a safe way.

    This function returns the class represented by the given model
    if it exists in 'treemap.models'
    """
    # All of our models live in 'treemap.models', so
    # we can start with that namespace
    models_module = __import__('treemap.models')

    if not hasattr(models_module.models, model_string):
        raise ValidationError(trans('invalid model type'))

    return getattr(models_module.models, model_string)


class HttpBadRequestException(Exception):
    pass


class InvalidInstanceException(Exception):
    pass


def require_http_method(method):
    return require_http_methods([method])


def add_visited_instance(request, instance):
    visited_instances = request.session.get('visited_instances', OrderedDict())

    if instance.pk in visited_instances:
        del visited_instances[instance.pk]
    visited_instances[instance.pk] = datetime.datetime.now()

    request.session['visited_instances'] = visited_instances
    request.session.modified = True


def get_last_visited_instance(request):
    if 'visited_instances' in request.session:
        instance_id = next(reversed(request.session['visited_instances']))
        return Instance.objects.get(pk=instance_id)
    else:
        return None


def login_redirect(request):
    # Reference: django/contrib/auth/decorators.py
    path = request.build_absolute_uri()
    # urlparse chokes on lazy objects in Python 3, force to str
    resolved_login_url = force_str(
        resolve_url(settings.LOGIN_URL))
    # If the login url is the same scheme and net location then just
    # use the path as the "next" url.
    login_scheme, login_netloc = urlparse(resolved_login_url)[:2]
    current_scheme, current_netloc = urlparse(path)[:2]
    if (not login_scheme or login_scheme == current_scheme)\
    and (not login_netloc or login_netloc == current_netloc):  # NOQA
        path = request.get_full_path()
    from django.contrib.auth.views import redirect_to_login
    return redirect_to_login(
        path, resolved_login_url, REDIRECT_FIELD_NAME)


def instance_request(view_fn):
    @wraps(view_fn)
    def wrapper(request, instance_url_name, *args, **kwargs):
        instance = get_object_or_404(Instance, url_name=instance_url_name)
        # Include the instance as both a request property and as an
        # view function argument for flexibility and to keep "template
        # only" requests simple.
        request.instance = instance

        user = request.user
        if user.is_authenticated():
            instance_user = user.get_instance_user(instance)
            request.instance_user = instance_user

        if instance.is_accessible_by(request.user):
            add_visited_instance(request, instance)
            return view_fn(request, instance, *args, **kwargs)
        else:
            if request.user.is_authenticated():
                return HttpResponseRedirect(reverse('instance_not_available'))
            else:
                return login_redirect(request)

    return wrapper


def strip_request(view_fn):
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        return view_fn(*args, **kwargs)

    return wrapper


def render_template(templ, callable_or_dict=None, **kwargs):
    """
    takes a template to render to and an object to render
    the data for this template.

    If callable_or_dict is callable, it will be called with
    the request and any additional arguments to produce the
    template paramaters. This is useful for a view-like function
    that returns a dict-like object instead of an HttpResponse.

    Otherwise, callable_or_dict is used as the parameters for
    the rendered response.
    """
    def wrapper(request, *args, **wrapper_kwargs):
        if callable(callable_or_dict):
            params = callable_or_dict(request, *args, **wrapper_kwargs)
        else:
            params = callable_or_dict

        # If we want to return some other response
        # type we can, that simply overrides the default
        # behavior
        if params is None or isinstance(params, dict):
            return render_to_response(templ, params,
                                      RequestContext(request), **kwargs)
        else:
            return params

    return wrapper


def json_api_call(req_function):
    """ Wrap a view-like function that returns an object that
        is convertable from json
    """
    @wraps(req_function)
    def newreq(request, *args, **kwargs):
        outp = req_function(request, *args, **kwargs)
        if issubclass(outp.__class__, HttpResponse):
            return outp
        else:
            return '%s' % json.dumps(outp)
    return string_as_file_call("application/json", newreq)


def string_as_file_call(content_type, req_function):
    """
    Wrap a view-like function that returns a string and marshalls it into an
    HttpResponse with the given Content-Type
    """
    @wraps(req_function)
    def newreq(request, *args, **kwargs):
        try:
            outp = req_function(request, *args, **kwargs)
            if issubclass(outp.__class__, HttpResponse):
                response = outp
            else:
                response = HttpResponse()
                response.write(outp)
                response['Content-length'] = str(len(response.content))

            response['Content-Type'] = content_type

        except HttpBadRequestException, bad_request:
            response = HttpResponseBadRequest(bad_request.message)

        return response
    return newreq


def bad_request_json_response(message=None, validation_error_dict=None):
    if message is None:
        message = 'One or more of the specified values are invalid.'
    response = HttpResponse()
    response.status_code = 400
    content = {'error': message}
    if validation_error_dict:
        content['validationErrors'] = validation_error_dict
    response.write(json.dumps(content))
    response['Content-length'] = str(len(response.content))
    response['Content-Type'] = "application/json"
    return response


def package_validation_errors(model_name, validation_error):
    """
    validation_error contains a dictionary of error messages of the form
    {fieldname1: [messages], fieldname2: [messages]}.
    Return a version keyed by "modelname.fieldname" instead of "fieldname".
    """
    return {'%s.%s' % (model_name.lower(), field): msgs
            for (field, msgs) in validation_error.message_dict.iteritems()}


# https://docs.djangoproject.com/en/dev/topics/serialization/#id2
class LazyEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Promise):
            return force_text(obj)
        return super(LazyEncoder, self).default(obj)


def return_400_if_validation_errors(req):
    def run_and_catch_validations(*args, **kwargs):
        try:
            return req(*args, **kwargs)
        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                message_dict = e.message_dict
            else:
                message_dict = {'errors': e.messages}

            return HttpResponseBadRequest(
                json.dumps(message_dict, cls=LazyEncoder))

    return run_and_catch_validations


def save_uploaded_image(image_data, name_prefix, thumb_size=None):
    try:
        image = Image.open(image_data)
        image.verify()
    except IOError:
        raise ValidationError('Invalid image')

    try:
        hash = hashlib.md5(image_data.read()).hexdigest()
        name = "%s-%s.%s" % (name_prefix, hash, image.format.lower())

        image_file = File(image_data)
        image_file.name = name
        thumb_file = None

        if thumb_size is not None:
            # http://www.pythonware.com/library/pil/handbook/image.htm
            # ...if you need to load the image after using this method,
            # you must reopen the image file.
            image_data.seek(0)
            image = Image.open(image_data)
            image.thumbnail(thumb_size, Image.ANTIALIAS)
            temp = StringIO()
            image.save(temp, format=image.format)
            temp.seek(0)
            thumb_file = SimpleUploadedFile(
                'thumb-' + name, temp.read(),
                'image/%s' % image.format.lower())

        # Reset image position
        image_data.seek(0)

        return image_file, thumb_file
    except:
        raise ValidationError('Could not upload image')
