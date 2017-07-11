"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    toastr = require('toastr'),
    BU = require('treemap/lib/baconUtils.js'),
    urlState = require('treemap/lib/urlState.js'),
    ModelingUrls = require('modeling/lib/modelingUrls.js');

var dom = {
    container: '#plan-list',
    content: '.loaded-content',
    spinner: '.loading-content',
    plansBackdrop: '.plans-backdrop',
    btnClose: '.plans-header .close',
    btnLoadPlan: '.load-plan',
    btnDeletePlan: '.delete-plan',
    btnNewPlan: '.new-plan',
    deletePlanOkModal: '#confirmDeletePlan',
    btnDeletePlanOk: '#confirmDeletePlan .ok',
    filterButtons: '#plan-filters a',
    columnHeaders: '#plans-column-headers a',
    pagingButtons: '.pagination li a'
};

module.exports = {
    init: init,
    show: show
};

var _urls = null,
    _strings = null,
    $container;

function init(options) {
    _urls = new ModelingUrls(options.urls);
    _strings = options.strings;

    // Use event delegation on the outer container, because we replace
    // the entire table including the pagination and filter section.
    $container = $(dom.container);

    var currentPlanIdProperty = options.currentPlanIdProperty,
        closeStream = Bacon.mergeAll(
            $container.asEventStream('click', dom.btnClose),
            $container.asEventStream('click', dom.plansBackdrop),
            $(window).asEventStream('keydown').filter(BU.isEscKey)
        );

    // Hide close button if no plan chosen
    currentPlanIdProperty.onValue($(dom.btnClose), 'toggle');

    closeStream
        .doAction('.preventDefault')
        .filter(currentPlanIdProperty) // prevent close if no plan chosen
        .onValue(hide);

    $container.asEventStream('click', dom.btnLoadPlan)
        .doAction('.preventDefault')
        .doAction(hide)
        .map(getPlanId)
        .onValue(loadPlan);

    BU.reloadContainerOnClick($container, dom.pagingButtons, dom.filterButtons, dom.columnHeaders);

    $container.asEventStream('click', dom.btnDeletePlan)
        .doAction('.preventDefault')
        .onValue(confirmDeletePlan);

    $(dom.btnDeletePlanOk).asEventStream('click')
        .onValue(deletePlan);

    // Note this "New Plan" button also shares a handler with the toolbar "New Plan" button
    $container.asEventStream('click', dom.btnNewPlan)
        .doAction('.preventDefault')
        .onValue(hide);
}

function show(options) {
    var refresh = options && options.refresh,
        refreshComplete = false;
    if (refresh) {
        $(dom.content).hide();
        $container.load(_urls.planListUrl(), function () {
            refreshComplete = true;
        });
    }
    $container.removeClass('slideUp').fadeIn(400, function () {
        if (refresh && !refreshComplete) {
            $(dom.spinner).show();
        }
    });
}

function hide() {
    $container.addClass('slideUp').fadeOut();
}

function getPlanId(jQueryEvent) {
    var $row = $(jQueryEvent.target).parents('[data-plan-id]');
    return $row.data('plan-id');
}

function loadPlan(planId) {
    urlState.set('planId', planId);
}

function confirmDeletePlan(e) {
    var planId = getPlanId(e);
    if (planId == urlState.get('planId')) {  // == on purpose so "1" == 1
        // For simplicity, prevent deleting the currently-loaded plan.
        // Disabling or hiding the "Delete" link would be nice, but the
        // plan list gets refreshed in many ways and the current plan ID
        // isn't always available (e.g. when paging). So show toast.
        toastr.error(_strings.CANT_DELETE_CURRENT_PLAN);
    } else {
        // Show confirmation modal, with context set on OK button
        var $okButton = $(dom.btnDeletePlanOk);
        $okButton.data('plan-id', planId);
        $okButton.data('query-string', $(e.target).data('query-string'));
        $(dom.deletePlanOkModal).modal('show');
    }
}

function deletePlan(e) {
    var $okButton = $(e.target),
        planId = $okButton.data('plan-id'),
        queryString = $okButton.data('query-string'),  // preserves page/filter/sort
        url = _urls.planUrl(planId) + queryString,
        responseStream = BU.ajaxRequest({
            url: url,
            method: 'DELETE'
        })();
    responseStream.onValue(function(html) {
        toastr.success(_strings.PLAN_DELETED);
        $container.html(html);
    });
    responseStream.onError(function(xhr) {
        toastr.error(_strings.DELETE_PLAN_ERROR);
    });
}
