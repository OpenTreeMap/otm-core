"use strict";

// The main "map" page has several modes -- browse trees, add a tree, and edit
// tree details. Each mode has a div in the sidebar to show its UI and a JS
// module to handle UI events. This module initializes the mode modules and
// orchestrates switching between modes.

var $                   = require('jquery'),
    _                   = require('lodash'),
    U                   = require('treemap/utility'),
    browseTreesMode     = require('treemap/browseTreesMode'),
    addTreeMode         = require('treemap/addTreeMode'),
    editTreeDetailsMode = require('treemap/editTreeDetailsMode'),
    addResourceMode     = require('treemap/addResourceMode'),
    inlineEditForm      = require('treemap/inlineEditForm'),
    mapState            = require('treemap/mapState'),
    plotMarker          = require('treemap/plotMarker'),
    statePrompter       = require('treemap/statePrompter'),
    prompter,
    currentMode;

var sidebarBrowseTrees          = '#sidebar-browse-trees',
    sidebarAddTree              = '#sidebar-add-tree',
    sidebarAddResource          = '#sidebar-add-resource',
    $treeDetailAccordionSection = U.$find('#tree-detail'),
    $fullDetailsButton          = U.$find('#full-details-button'),
    $treeDetailButtonGroup      = U.$find('#map-plot-details-button'),
    $exploreMapHeaderLink       = U.$find('.navbar li.explore-map'),
    $addFeatureHeaderLink       = U.$find('.navbar li[data-feature=add_plot]');

function activateMode(mode, sidebar, safeTransition) {

    // each mode activator takes an argument that determines
    // whether or not to lock the prompter, or in other words,
    // whether or not activateMode should prompt the user before
    // changing modes.
    if (safeTransition === true) {
        prompter.unlock();
    }
    if (mode !== currentMode &&
        prompter.canProceed()) {
        if (currentMode && currentMode.deactivate) {
            currentMode.deactivate();
        }
        $(sidebar).siblings().hide();
        $(sidebar).show();
        if (mode.activate) {
            mode.activate();
        }

        // lockOnActivate will specify whether to leave the
        // prompter in a locked state, which causes a
        // prompt on mode changes and page navigation.
        if (mode.lockOnActivate === true) {
            prompter.lock();
        } else {
            prompter.unlock();
        }
        mapState.setModeName(mode.name);
        currentMode = mode;
    }
}

function activateBrowseTreesMode(safeTranstion) {
    activateMode(browseTreesMode, sidebarBrowseTrees, safeTranstion);
}
function activateAddTreeMode(safeTranstion) {
    activateMode(addTreeMode, sidebarAddTree, safeTranstion);
}
function activateEditTreeDetailsMode(safeTranstion) {
    activateMode(editTreeDetailsMode, sidebarBrowseTrees, safeTranstion);
}
function activateAddResourceMode(safeTranstion) {
    activateMode(addResourceMode, sidebarAddResource, safeTranstion);
}

function inBrowseTreesMode() { return currentMode === browseTreesMode; }
function inAddTreeMode()     { return currentMode === addTreeMode; }
function inEditTreeMode()    { return currentMode === editTreeDetailsMode; }
function inAddResourceMode() { return currentMode === addResourceMode; }

function init(config, mapManager, triggerSearchBus) {
    // browseTreesMode and editTreeDetailsMode share an inlineEditForm,
    // so initialize it here.
    var form = inlineEditForm.init({
        config: config,
        updateUrl: '', // set in browseTreesMode.js on map click
        form: '#details-form',
        edit: '#quick-edit-button',
        save: '#save-details-button',
        cancel: '#cancel-edit-details-button',
        displayFields: sidebarBrowseTrees + ' [data-class="display"]',
        editFields: sidebarBrowseTrees + ' [data-class="edit"]',
        validationFields: sidebarBrowseTrees + ' [data-class="error"]',
        onSaveBefore: editTreeDetailsMode.onSaveBefore
    });

    prompter = statePrompter.init({
        warning: config.trans.exitWarning,
        question: config.trans.exitQuestion
    });

    form.inEditModeProperty.onValue(function (inEditMode) {
        // Form is changing to edit mode or display mode
        if (inEditMode) {
            activateEditTreeDetailsMode(true);
        } else {
            activateBrowseTreesMode(true);
        }
    });

    plotMarker.init(config, mapManager.map);

    browseTreesMode.init({
        config: config,
        map: mapManager.map,
        inMyMode: inBrowseTreesMode,
        $treeDetailAccordionSection: $treeDetailAccordionSection,
        $fullDetailsButton: $fullDetailsButton,
        inlineEditForm: form,
        plotMarker: plotMarker,
        $buttonGroup: $treeDetailButtonGroup
    });

    addTreeMode.init({
        config: config,
        $addFeatureHeaderLink: $addFeatureHeaderLink,
        $exploreMapHeaderLink: $exploreMapHeaderLink,
        mapManager: mapManager,
        plotMarker: plotMarker,
        inMyMode: inAddTreeMode,
        sidebar: sidebarAddTree,
        onClose: _.partial(activateBrowseTreesMode, true),
        formSelector: '#add-tree-form',
        validationFields: '#add-tree-container [data-class="error"]',
        indexOfSetLocationStep: 0,
        typeaheads: [getSpeciesTypeaheadOptions(config, "add-tree-species")],
        addFeatureRadioOptions: 'addFeatureOptions',
        triggerSearchBus: triggerSearchBus
    });

    editTreeDetailsMode.init({
        config: config,
        mapManager: mapManager,
        inlineEditForm: form,
        plotMarker: plotMarker,
        inMyMode: inEditTreeMode,
        typeaheads: [getSpeciesTypeaheadOptions(config, "edit-tree-species")]
    });

    addResourceMode.init({
        config: config,
        $addFeatureHeaderLink: $addFeatureHeaderLink,
        $exploreMapHeaderLink: $exploreMapHeaderLink,
        mapManager: mapManager,
        plotMarker: plotMarker,
        inMyMode: inAddResourceMode,
        sidebar: sidebarAddResource,
        onClose: _.partial(activateBrowseTreesMode, true),
        formSelector: '#add-resource-form',
        validationFields: '#add-resource-container [data-class="error"]',
        indexOfSetLocationStep: 1,
        addFeatureRadioOptions: 'addResourceOptions',
        triggerSearchBus: triggerSearchBus
    });
}

function getSpeciesTypeaheadOptions(config, idPrefix) {
    return {
        name: "species-edit",
        url: config.instance.url + "species/",
        input: "#" + idPrefix + "-typeahead",
        template: "#species-element-template",
        hidden: "#" + idPrefix + "-hidden",
        reverse: "id",
        forceMatch: true,
        minLength: 1
    };
}

module.exports = {
    init: init,
    activateBrowseTreesMode: activateBrowseTreesMode,
    activateAddTreeMode: activateAddTreeMode,
    activateAddResourceMode: activateAddResourceMode
};
