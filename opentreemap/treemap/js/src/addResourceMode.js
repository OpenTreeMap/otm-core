"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    U = require('treemap/utility'),
    addMapFeature = require('treemap/addMapFeature');

var manager,
    STEP_CHOOSE_TYPE = 0,
    STEP_LOCATE = 1,
    STEP_DETAILS = 2,
    STEP_FINAL = 3;

function init(options) {
    var config = options.config,
        $sidebar = $(options.sidebar),
        $resourceType = U.$find('input[name="addResourceType"]', $sidebar),
        $form = U.$find(options.formSelector, $sidebar),
        $summaryHead = U.$find('.summaryHead', $sidebar),
        $summarySubhead = U.$find('.summarySubhead', $sidebar);

    manager = addMapFeature.init(options);

    $resourceType.on('change', onResourceTypeChosen);

    manager.addFeatureStream.onValue(initSteps);
    manager.deactivateStream.onValue(initSteps);

    function onResourceTypeChosen() {
        var type = $resourceType.filter(':checked').val(),
            typeName = $resourceType.filter(':checked').next().text().trim(),
            addFeatureUrl = config.instance.url + 'features/' + type + '/';
        if (type) {
            manager.setAddFeatureUrl(addFeatureUrl);
            manager.stepControls.enableNext(STEP_CHOOSE_TYPE, true);
            manager.stepControls.enableNext(STEP_DETAILS, false);
            $summaryHead.text(typeName);
            $summarySubhead.text("Resource");
            $.ajax({
                url: config.instance.url + "features/" + type + '/',
                type: 'GET',
                dataType: 'html',
                success: onResourceFormLoaded
            });
        }
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
        $resourceType.prop('checked', false);
        manager.stepControls.enableNext(STEP_CHOOSE_TYPE, false);
        hideSubquestions();
    }

    function hideSubquestions() {
        U.$find('.resource-subquestion', $form).hide();
    }

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
}

function activate() {
    if (manager) {
        manager.activate();
        manager.stepControls.enableNext(STEP_CHOOSE_TYPE, false);
    }
}

function deactivate() {
    if (manager) {
        manager.deactivate();
    }
}

module.exports = {
    name: 'addResource',
    init: init,
    activate: activate,
    deactivate: deactivate,
    lockOnActivate: true
};
