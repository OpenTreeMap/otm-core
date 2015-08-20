"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    L = require('leaflet'),
    U = require('treemap/utility'),
    addMapFeature = require('treemap/addMapFeature'),
    polylineEditor = require('treemap/polylineEditor');

var activateMode = _.identity,
    deactivateMode = _.identity,
    STEP_CHOOSE_TYPE = 0,
    STEP_LOCATE = 1,
    STEP_OUTLINE_AREA = 2,
    STEP_DETAILS = 3,
    STEP_FINAL = 4;

function init(options) {
    options.onSaveBefore = onSaveBefore;
    var manager = addMapFeature.init(options),
        config = options.config,
        $sidebar = $(options.sidebar),
        $footerStepCounts = U.$find('.footer-total-steps', $sidebar),
        $resourceType = U.$find('input[name="addResourceType"]', $sidebar),
        $form = U.$find(options.formSelector, $sidebar),
        $summaryHead = U.$find('.summaryHead', $sidebar),
        $summarySubhead = U.$find('.summarySubhead', $sidebar),
        $continueLink = $('#addresource-viewdetails'),
        mapManager = options.mapManager,
        plotMarker = options.plotMarker,
        areaFieldIdentifier,
        editor = polylineEditor(options),
        onlyOneResourceType = $resourceType.length === 1;

    $resourceType.on('change', onResourceTypeChosen);

    manager.addFeatureStream.onValue(initSteps);
    manager.deactivateStream.onValue(initSteps);

    activateMode = function() {
        manager.activate();
        plotMarker.useTreeIcon(false);
        initSteps();
    };

    deactivateMode = function () {
        editor.removeAreaPolygon();
        manager.deactivate();
    };

    function onResourceTypeChosen() {
        var $option = $resourceType.filter(':checked'),
            type = $option.val(),
            typeName = $option.next().text().trim(),
            areaFieldName = $option.data('area-field-name'),
            skipDetailForm = $option.data('skip-detail-form') == 'True',
            enableContinueEditing = $option.data('is-editable') == 'True',
            addFeatureUrl = config.instance.url + 'features/' + type + '/';
        if (type) {
            manager.setAddFeatureUrl(addFeatureUrl);
            manager.stepControls.enableNext(STEP_CHOOSE_TYPE, true);
            manager.stepControls.enableNext(STEP_OUTLINE_AREA, true);
            manager.stepControls.enableNext(STEP_DETAILS, false);
            $summaryHead.text(typeName);

            var hasAreaStep = !!areaFieldName;
            activateStep(STEP_OUTLINE_AREA, hasAreaStep);
            activateStep(STEP_DETAILS, !skipDetailForm);
            if (hasAreaStep) {
                var objectName = type.slice(0, 1).toLowerCase() + type.slice(1);
                areaFieldIdentifier = objectName + '.' + areaFieldName;
            } else {
                areaFieldIdentifier = null;
            }
            editor.removeAreaPolygon(); // in case user backed up and changed type
            if (enableContinueEditing) {
                $continueLink.removeClass('disabled');
                $continueLink.prop('disabled', false);
            } else {
                $continueLink.addClass('disabled');
                $continueLink.prop('disabled', true);
            }

            $.ajax({
                url: config.instance.url + "features/" + type + '/',
                type: 'GET',
                dataType: 'html',
                success: onResourceFormLoaded
            });
        }
    }

    function activateStep(step, shouldActivate) {
        var stepCount = manager.stepControls.maxStepNumber + 1;
        if (!shouldActivate) {
            stepCount--;
        }
        $footerStepCounts.each(function () {
            $(this).text(stepCount);
        });
        manager.stepControls.activateStep(step, shouldActivate);
    }

    function onResourceFormLoaded(html) {
        $form.html(html);
        U.$find('[data-class="edit"]', $form).show();
        U.$find('[data-class="display"]', $form).hide();
        hideSubquestions();

        U.$find('input[type="radio"]', $form).on('change', onQuestionAnswered);
        U.$find('input[type="text"]', $form).on('keyup', enableFinalStep);
        U.$find('select', $form).on('change', enableFinalStep);
    }

    function initSteps() {
        plotMarker.hide();
        editor.removeAreaPolygon();
        hideSubquestions();
        if (onlyOneResourceType) {
            onResourceTypeChosen();
        } else {
            $resourceType.prop('checked', false);
            manager.stepControls.enableNext(STEP_CHOOSE_TYPE, false);
        }
    }

    function hideSubquestions() {
        U.$find('.resource-subquestion', $form).hide();
    }

    manager.stepControls.stepChangeCompleteStream.onValue(function (stepNumber) {
        if (stepNumber === STEP_LOCATE) {
            if (plotMarker.wasMoved()) {
                plotMarker.enableMoving({needsFirstMove: false});
            } else {
                // Let user start creating a feature (by clicking the map)
                plotMarker.enablePlacing();
            }
        } else {
            plotMarker.disableMoving();
        }

        if (stepNumber === STEP_OUTLINE_AREA) {
            editor.enableAreaPolygon({plotMarker: plotMarker});
        } else {
            editor.disableAreaPolygon();
        }
    });


    function onQuestionAnswered(e) {
        var $radioButton = $(e.target),
            onOrOff = $radioButton.val() === 'True',
            $container = $radioButton.closest('.resource-question, .resource-subquestion'),
            $subquestions = $container.children('.resource-subquestion');
        $subquestions.toggle(onOrOff);
        enableFinalStep();
    }

    function enableFinalStep() {
        var $questions = $form.find('.resource-question, .resource-subquestion:visible'),
            $fieldGroups = $questions.children('.field-edit'),
            values = $fieldGroups
                .find('input[type!=radio],select')
                .serializeArray(),
            answered = _.map(values, function (value) {
                return value.value.trim().length > 0;
            }),
            $fieldGroupsRadio = $fieldGroups.filter(':has(input[type=radio])'),
            $checked = $fieldGroupsRadio.find(':checked'),
            allAnswered = _.every(answered) && $fieldGroupsRadio.length === $checked.length;

        manager.stepControls.enableNext(STEP_DETAILS, allAnswered);
    }

    function onSaveBefore(formData) {
        if (areaFieldIdentifier) {
            formData[areaFieldIdentifier] = {polygon: editor.getPoints()};
        }
    }
}

function activate() {
    activateMode();
}

function deactivate() {
    deactivateMode();
}

module.exports = {
    name: 'addResource',
    init: init,
    activate: activate,
    deactivate: deactivate,
    lockOnActivate: true
};
