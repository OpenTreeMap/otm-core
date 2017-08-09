# -*- coding: utf-8 -*-
from functools import partial

from django.contrib.auth.decorators import login_required

from django_tinsel.utils import decorate as do
from django_tinsel.decorators import route, json_api_call, render_template


from treemap.decorators import (instance_request, json_api_edit,
                                return_400_if_validation_errors, login_or_401,
                                requires_permission)

from modeling.views import (get_plans_context, get_modeling_context,
                            add_plan, update_plan, delete_plan, get_plan,
                            run_model, get_boundaries_at_point)


def modeling_instance_request(view_fn, redirect=True):
    return do(
        partial(instance_request, redirect=redirect),
        requires_permission('modeling'),
        view_fn)


modeling_view = do(
    login_required,
    modeling_instance_request,
    render_template('modeling/modeling.html'),
    get_modeling_context)


get_boundaries_at_point_view = do(
    login_or_401,
    json_api_call,
    modeling_instance_request,
    get_boundaries_at_point)


run_model_view = do(
    login_or_401,
    json_api_call,
    modeling_instance_request,
    run_model)


plan_view = do(
    login_or_401,
    modeling_instance_request,
    route(
        GET=do(json_api_call, get_plan),
        PUT=do(
            json_api_edit,
            return_400_if_validation_errors,
            update_plan),
        DELETE=do(
            render_template('modeling/partials/plans/plans.html'),
            delete_plan)))


plans_view = do(
    login_or_401,
    modeling_instance_request,
    route(
        GET=do(
            render_template('modeling/partials/plans/plans.html'),
            get_plans_context),
        POST=do(json_api_edit,
                return_400_if_validation_errors,
                add_plan)))
