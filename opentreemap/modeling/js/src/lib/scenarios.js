"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    scenarioUi = require('modeling/lib/scenarioUi.js'),
    template = require('modeling/lib/template.js');

module.exports = {
    getEmpty: getEmpty,
    init: init,
    all: all
};

var initialized = false,
    scenarioStateInterface,
    scenariosList = [],
    defaultModelParams,
    currentScenarioId = null;

var dom = {
    viewPrioritiesButton: '.view-priorities-button',
    viewScenarioButton: '#scenario-buttons .js-scenario',
    viewScenarioControl: '.js-view-scenario', // buttons and hamburger entries
    scenarioChooser: '#scenario-buttons',
    addScenarioButton: '.add-scenario',
    scenarioMenu: '#view-switcher .dropdown-menu',
    scenarioItems: '#view-switcher .dropdown-menu li:not(:first)',
    scenarioActionRename: '.js-rename-scenario',
    scenarioActionDuplicate: '.js-duplicate-scenario',
    scenarioActionDelete: '.js-delete-scenario',
    renameDialog: '#renameScenario',
    renameDialogOK: '#renameScenario .ok',
    renameDialogScenarioName: '#edit-scenario-name'
};

var templates = {
    scenarioButton: '#scenario-button-tmpl',
    scenarioMenuItem: '#scenario-menu-item-tmpl'
};

function init(planState, options) {
    defaultModelParams = options.defaultModelParams;
    scenarioStateInterface = scenarioUi.init(options);

    planState.scenariosStream
        .onValue(loadScenarios);

    $(dom.viewPrioritiesButton)
        .asEventStream('click')
        .onValue(setCurrentScenarioId, null);

    handleScenarioChange();
    handleScenarioUpdate();
    handleAddScenario();
    handleDuplicateScenario();
    handleDeleteScenario();

    initialized = true;

    var saveNeededStream =
            Bacon.mergeAll(
                scenarioStateInterface.serializedProperty.changes(),
                handleRenameScenario()
            ).map(true);
    return {
        addScenario: addScenario,
        saveNeededStream: saveNeededStream
    };
}

function loadScenarios(scenarios) {
    if (initialized) {
        scenariosList = scenarios ? _.clone(scenarios.scenarios) : [];
        updateScenarioButtons();
        setCurrentScenarioId(scenarios.currentScenarioId);
    }
}

function getEmpty() {
    return {
        scenarios: [],
        currentScenarioId: null
    };
}

function all() {
    return {
        scenarios: scenariosList,
        currentScenarioId: currentScenarioId
    };
}

function handleScenarioChange() {
    $(dom.scenarioChooser).add($(dom.scenarioMenu))
        .asEventStream('click', dom.viewScenarioControl)
        .map(getScenarioIdFromEvent)
        .onValue(setCurrentScenarioId);
}

function loadScenario(idString) {
    if (idString === '_') {
        // Plan request pending; scenario unknown
        return;
    }
    var id = parseInt(idString, 10),
        index = getScenarioIndex(id),
        isValidScenario = (index >= 0);
    if (isValidScenario) {
        scenarioStateInterface.load(scenariosList[index]);
    } else {
        scenarioStateInterface.reset();
    }
    highlightViewButton(index);
    return isValidScenario;
}

function handleScenarioUpdate() {
    // As user modifies scenario, update serialized version
    scenarioStateInterface.serializedProperty
        .onValue(updateScenario);

    function updateScenario(scenario) {
        if (scenario.name !== undefined) { // ignore initial dummy scenario
            var index = getScenarioIndex(scenario.id);
            scenariosList[index] = scenario;
        }
    }
}

function handleAddScenario() {
    $(dom.addScenarioButton)
        .asEventStream('click')
        .onValue(addScenario);

}

function addScenario() {
    var id = (scenariosList.length === 0) ? 1 : getNextScenarioId(),
        scenario = {
            id: id,
            name: 'Scenario ' + id,
            model_params: _.cloneDeep(defaultModelParams),
            replanting: {
                enable: false,
                nYears: 2
            }
        };
    scenariosList.push(scenario);
    updateScenarioButtons();
    scenarioStateInterface.reset(scenario);
    setCurrentScenarioId(id);
}

function getNextScenarioId() {
    var id = _.max(_.map(scenariosList, 'id')) + 1;
    return id;
}

function handleRenameScenario() {
    handleScenarioAction(dom.scenarioActionRename, showRenameDialog);

    function showRenameDialog(index) {
        var scenario = scenariosList[index];
        $(dom.renameDialogScenarioName).val(scenario.name);
        $(dom.renameDialogOK).data('id', scenario.id);
        $(dom.renameDialog).modal('show');
    }

    var scenarioRenamedStream = $(dom.renameDialogOK).asEventStream('click');
    scenarioRenamedStream
        .map(getScenarioIndexFromEvent)
        .onValue(renameScenario);

    function renameScenario(index) {
        var newName = $(dom.renameDialogScenarioName).val().trim();
        if (newName.length > 0) {
            scenariosList[index].name = newName;
            updateScenarioButtons(index);
        }
    }
    return scenarioRenamedStream;
}

function handleDuplicateScenario() {
    handleScenarioAction(dom.scenarioActionDuplicate, duplicateScenario);

    function duplicateScenario(index) {
        var scenario = _.cloneDeep(scenariosList[index]);
        scenario.id = getNextScenarioId();
        scenario.name = "Copy of " + scenario.name;
        scenariosList.splice(index + 1, 0, scenario);
        updateScenarioButtons();
        setCurrentScenarioId(scenario.id);
    }
}

function handleDeleteScenario() {
    handleScenarioAction(dom.scenarioActionDelete, deleteScenario);

    function deleteScenario(index) {
        var message = 'Really delete scenario "' + scenariosList[index].name + '"?';
        if (window.confirm(message)) {
            scenariosList.splice(index, 1);
            if (index === scenariosList.length) {
                index--;
            }
            updateScenarioButtons(index);
            var id = (index < 0 ? null : scenariosList[index].id);
            setCurrentScenarioId(id);
        }
    }
}

function handleScenarioAction(selector, handler) {
    $(dom.scenarioChooser)
        .asEventStream('click', selector)
        .map(getScenarioIndexFromEvent)
        .onValue(handler);
}

function getScenarioIndexFromEvent(e) {
    var id = getScenarioIdFromEvent(e),
        index = getScenarioIndex(id);
    return index;
}

function getScenarioIdFromEvent(e) {
    var id = $(e.target).data('id');
    return id;
}

function getScenarioIndex(id) {
    return _.findIndex(scenariosList, {id: id});
}

function highlightViewButton(index) {
    var $scenarioButtons = $(dom.viewScenarioButton),
        $prioritiesButton = $(dom.viewPrioritiesButton);
    $scenarioButtons.removeClass('active');
    $prioritiesButton.removeClass('active');
    if (index >= 0) {
        $scenarioButtons.eq(index).addClass('active');
    } else {
        $prioritiesButton.addClass('active');
    }
}

function setCurrentScenarioId(id) {
    currentScenarioId = id;
    loadScenario(id);
}

function updateScenarioButtons(index) {
    var $buttons = $(dom.scenarioChooser).empty(),
        $menu = $(dom.scenarioMenu);
    $(dom.scenarioItems).remove();
    _.each(scenariosList, function (scenario) {
        var info = {name: scenario.name, id: scenario.id};
        $buttons.append(template.render(templates.scenarioButton, info));
        $menu.append(template.render(templates.scenarioMenuItem, info));
    });
    if (scenariosList.length > 0) {
        scenarioUi.show();
    }
    if (scenariosList.length === 1) {
        // Prevent deleting the only scenario
        $(dom.scenarioActionDelete).closest('li').remove();
    }
    if (!_.isUndefined(index)) {
        highlightViewButton(index);
    }
}
