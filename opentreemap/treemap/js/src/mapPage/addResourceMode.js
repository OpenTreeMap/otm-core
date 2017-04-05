"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    U = require('treemap/lib/utility.js'),
    addMapFeature = require('treemap/mapPage/addMapFeature.js'),
    polylineEditor = require('treemap/lib/polylineEditor.js'),
    plotMarker = require('treemap/lib/plotMarker.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

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
        $sidebar = $(options.sidebar),
        $footerStepCounts = U.$find('.footer-total-steps', $sidebar),
        $resourceType = U.$find('input[name="addResourceType"]', $sidebar),
        $form = U.$find(options.formSelector, $sidebar),
        $summaryHead = U.$find('.summaryHead', $sidebar),
        $continueLink = $('#addresource-viewdetails'),
        areaFieldIdentifier,
        editor = polylineEditor(options),
        onlyOneResourceType = $resourceType.length === 1;

    $resourceType.on('change', onResourceTypeChosen);

    manager.addFeatureStream.onValue(initSteps);
    manager.deactivateStream.onValue(initSteps);

    activateMode = function(type) {
        manager.activate();
        plotMarker.useTreeIcon(false);
        initSteps(type);
        $('body').addClass('add-feature');
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
            enableDetailNext = $option.data('enable-detail-next') == 'True',
            enableContinueEditing = $option.data('is-editable') == 'True',
            addFeatureUrl = reverse.add_map_feature({
                instance_url_name: config.instance.url_name,
                type: type
            });
        if (type) {
            manager.setAddFeatureUrl(addFeatureUrl);
            manager.stepControls.maxStepNumber = manager.stepControls.initialMaxStepNumber;
            manager.stepControls.enableNext(STEP_CHOOSE_TYPE, true);
            manager.stepControls.enableNext(STEP_OUTLINE_AREA, true);
            manager.stepControls.enableNext(STEP_DETAILS, enableDetailNext);
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
                url: reverse.add_map_feature({
                    instance_url_name: config.instance.url_name,
                    type: type
                }),
                type: 'GET',
                dataType: 'html',
                success: onResourceFormLoaded
            });
        }
    }

    function activateStep(step, shouldActivate) {
        if (!shouldActivate) {
            manager.stepControls.maxStepNumber--;
        }
        $footerStepCounts.each(function () {
            $(this).text(manager.stepControls.maxStepNumber + 1);
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

    function initSteps(type) {
        plotMarker.hide();
        editor.removeAreaPolygon();
        editor.areaStream.onValue($('.js-area'), 'html');
        hideSubquestions();
        var $type = _.isUndefined(type) ? $() : $resourceType.filter('[value="' + type + '"]');
        if ($type.length === 1) {
            $type.prop('checked', true);
            onResourceTypeChosen();
        } else if (onlyOneResourceType) {
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

function activate(options) {
    activateMode(options.mapFeatureType);
}

function deactivate() {
    deactivateMode();
}

module.exports = {
    name: 'addResource',
    hideSearch: true,
    init: init,
    activate: activate,
    deactivate: deactivate,
    lockOnActivate: true
};
