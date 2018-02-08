"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    L = require('leaflet'),
    U = require('treemap/lib/utility.js'),
    toastr = require('toastr'),
    MapPage = require('treemap/lib/mapPage.js'),
    ModelingUrls = require('modeling/lib/modelingUrls.js'),
    urlState = require('treemap/lib/urlState.js'),
    PlanState = require('modeling/lib/planState.js'),
    planList = require('modeling/lib/planList.js'),
    detailsDialog = require('modeling/lib/detailsDialog.js'),
    scenarioUi = require('modeling/lib/scenarioUi.js'),
    scenarios = require('modeling/lib/scenarios.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

$.ajaxSetup(require('treemap/lib/csrf.js').jqueryAjaxSetupOptions);

var dom = {
    toolbar: '#toolbar',
    btnSaveAs: '#toolbar .save-as',
    btnOpen: '#toolbar .open',
    btnCreate: '.new-plan',  // button on both toolbar and "open plan" dialog
    btnEditDetails: '#toolbar .edit',
    staleRevisionDialog: '#stale-revision-dialog',
    staleRevisionDialogOk: '#stale-revision-dialog .ok',
    modelName: '#model-name',
    modelVisibility: '#model-visibility',
    modelVisibilityText: '#model-visibility-text',
    autosaveMessage: '#autosave-message',
    noRegionModal: '#noRegion',
    scenarioPrioritizationLink: '#scenario-prioritization-link'
};

var _strings = window.modelingOptions.strings,
    // Push something to this stream to cancel sidebar actions.
    _interruptBus = new Bacon.Bus();

var NEW_PLAN = 'newPlan',
    EDIT_PLAN_DETAILS = 'editPlanDetails',
    SAVE_PLAN_AS = 'savePlanAs';

function init() {
    var $noRegionModal = $(dom.noRegionModal);
    if ($noRegionModal.data('itree-region-count') === 0) {
        $noRegionModal.on('hidden.bs.modal', function () {
            window.location.href = reverse.map(config.instance.url_name);
        });
        $noRegionModal.modal('show');
        return;
    }

    var options = window.modelingOptions,

        planState = new PlanState({
            urls: new ModelingUrls(options.urls),
            emptyScenarios: scenarios.getEmpty(),
            username: options.username
        }),

        mapPage = MapPage.init({
            domId: 'map',
            trackZoomLatLng: true,
            zoomLatLngInputStream: planState.zoomLatLngLoadedStream,
            plotLayerViewOnly: true
        }),

        currentPlanIdProperty = urlState.stateChangeStream
            .map(urlState, 'get', 'planId')
            .skipDuplicates()
            .toProperty(),

        zoomLatLngChangedStream = mapPage.zoomLatLngOutputStream
            .filter(planState, 'setZoomLatLng');

    options = _.defaults(options, {
        map: mapPage.map,
        mapManager: mapPage.mapManager,
        interruptStream: _interruptBus.toEventStream(),
        currentPlanIdProperty: currentPlanIdProperty
    });

    planList.init(options);

    var scenariosInterface = scenarios.init(planState, options);

    handleUrlPlanChange(planState, currentPlanIdProperty);
    handleToolbar(planState, scenariosInterface);
    handleDetailsChanged(planState);
    handleStaleRevision(planState);
    handleSaveResults(planState);

    var saveNeededStream = Bacon.mergeAll(
            scenariosInterface.saveNeededStream,
            planState.detailsStream,
            zoomLatLngChangedStream
        );
    saveNeededStream
        .filter(planState.shouldAutosaveProperty)
        .doAction(showAutosaveMessage, _strings.SAVING)
        // Debounce to prevent repeated autosaves from e.g. multiple clicks on
        // a number input spinner, or multiple stream events from a scenario switch.
        // Also allows the "Saving..." message to be seen rather than being
        // replaced immediately by the "All changes saved" message.
        .debounce(500)
        .onValue(function () {
            save(planState);
        });

    U.modalsFocusOnFirstInputWhenShown();

    urlState.init();  // must happen after URL state handlers are set up
    showPlanListIfNoPlanChosen();
    appendCenterToPrioritizationLink();
}

function appendCenterToPrioritizationLink() {
    var instanceCenter = window.otm.settings.instance.center,
        center = L.Projection.SphericalMercator.unproject(
            L.point(instanceCenter.x, instanceCenter.y)),
        prioritizationHref = $(dom.scenarioPrioritizationLink).attr('href');
    $(dom.scenarioPrioritizationLink).attr('href', prioritizationHref + '?center=' + center.lat + ',' + center.lng);
}

function showPlanListIfNoPlanChosen() {
    if (!urlState.get('planId')) {
        planList.show();
    }
}

function handleUrlPlanChange(planState, currentPlanIdProperty) {
    currentPlanIdProperty.onValue(loadPlanId);

    function loadPlanId(planIdString) {
        var planId = parseInt(planIdString, 10);
        if (_.isFinite(planId) && planId !== planState.id) {
            loadPlan(planId, planState);
        }
    }
}

function loadPlan(planId, planState) {
    var responseStream = planState.load(planId);
    responseStream.onValue(showAutosaveMessage, '');
    responseStream.errors()
        .mapError(_strings.LOAD_PLAN_ERROR)
        .onValue(displayResponseError);
}

function handleToolbar(planState, scenariosInterface) {
    clickStreamForToolbarButton(dom.btnOpen)
        .onValue(planList, 'show', {refresh: true});

    handleButton(dom.btnCreate, NEW_PLAN,
        _strings.NEW_PLAN, _strings.CREATE_NEW_PLAN, planState.getDefaultDetails());

    handleButton(dom.btnEditDetails, EDIT_PLAN_DETAILS,
        _strings.EDIT_PLAN_DETAILS, _strings.UPDATE_DETAILS);

    handleButton(dom.btnSaveAs, SAVE_PLAN_AS, _strings.SAVE_PLAN_AS, _strings.SAVE);

    function handleButton(button, operation, title, btnOkLabel, details) {
        clickStreamForToolbarButton(button)
            .onValue(function () {
                detailsDialog.show({
                    operation: operation,
                    details: details || planState.getDetails(),
                    title: title,
                    btnOkLabel: btnOkLabel
                });
            });
    }

    function clickStreamForToolbarButton(selector) {
        return $('body').asEventStream('click', selector)
            .doAction('.preventDefault')
            .doAction(_interruptBus, 'push');
    }

    var detailsDialogStreams = detailsDialog.init();

    detailsDialogStreams.planDetailsStream
        .onValue(function (newDetails) {
            var operation = newDetails.operation;
            if (operation === NEW_PLAN) {
                planState.reset();
                scenariosInterface.addScenario();
            } else if (operation === SAVE_PLAN_AS) {
                planState.clearId();
            }
            planState.setDetails(newDetails);
        });

    detailsDialogStreams.cancelStream
        .onValue(showPlanListIfNoPlanChosen);
}

function save(planState, forceUpdate) {
    planState.save(scenarios.all(), forceUpdate);
}

function handleSaveResults(planState) {
    planState.saveResultStream.onValue(function(data) {
        urlState.set('planId', planState.getId(), {silent: true});
        showAutosaveMessage(_strings.PLAN_SAVED);
    });

    planState.saveResultStream.onError(function(xhr) {
        if (xhr.status === 409) {
            $(dom.staleRevisionDialog).modal('show');
            showAutosaveMessage('');
        } else {
            showAutosaveMessage(_strings.SAVE_PLAN_UNKNOWN_ERROR);
        }
    });
}

function showAutosaveMessage(message) {
    $(dom.autosaveMessage).html(message);
}

function displayResponseError(message) {
    toastr.error(message);
}

function handleDetailsChanged(planState) {
    planState.detailsStream.onValue(function (details) {
        $(dom.modelName).text(details.name);
        if (details.isPublished) {
            $(dom.modelVisibilityText).text("PUBLIC");
            $(dom.modelVisibility).removeClass('private');
        } else {
            $(dom.modelVisibilityText).text("PRIVATE");
            $(dom.modelVisibility).addClass('private');
        }
    });
}

function handleStaleRevision(planState) {
    $(dom.staleRevisionDialogOk).on('click', function () {
        var option = $(dom.staleRevisionDialog).find(
            'input[name=staleRevisionOptions]:checked').val();
        if (option === 'saveAs') {
            detailsDialog.show({
                operation: SAVE_PLAN_AS,
                details: planState.getDetails(),
                title: _strings.SAVE_PLAN_AS,
                btnOkLabel: _strings.SAVE
            });
        } else if (option === 'useOther') {
            loadPlan(planState.getId(), planState);
        } else if (option === 'useMine') {
            save(planState, true /* force update */);
        }
    });
}

init();
