"use strict";

// The main "map" page has several modes -- browse trees, add a tree, and edit
// tree details. Each mode has a div in the sidebar to show its UI and a JS
// module to handle UI events. This module initializes the mode modules and
// orchestrates switching between modes.

var _                   = require('underscore'),
    U                   = require('treemap/utility'),
    browseTreesMode     = require('treemap/browseTreesMode'),
    addTreeMode         = require('treemap/addTreeMode'),
    editTreeDetailsMode = require('treemap/editTreeDetailsMode'),
    inlineEditForm      = require('treemap/inlineEditForm'),
    mapState            = require('treemap/mapState'),
    plotMarker          = require('treemap/plotMarker'),
    statePrompter       = require('treemap/statePrompter'),
    prompter,
    currentMode;

var $sidebarBrowseTrees         = U.$find('#sidebar-browse-trees'),
    $treeDetailAccordionSection = U.$find('#tree-detail'),
    $sidebarAddTree             = U.$find('#sidebar-add-tree'),
    $fullDetailsButton          = U.$find('#full-details-button'),
    $treeDetailButtonGroup      = U.$find('#map-plot-details-button'),
    $exploreTreesHeaderLink     = U.$find('.navbar li.explore-trees'),
    $addTreeHeaderLink          = U.$find('.navbar li[data-feature=add_plot]');

function activateMode(mode, $sidebar, safeTransition) {

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
        $sidebar.siblings().hide();
        $sidebar.show();
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
    activateMode(browseTreesMode, $sidebarBrowseTrees, safeTranstion);
}
function activateAddTreeMode(safeTranstion) {
    activateMode(addTreeMode, $sidebarAddTree, safeTranstion);
}
function activateEditTreeDetailsMode(safeTranstion) {
    activateMode(editTreeDetailsMode, $sidebarBrowseTrees, safeTranstion);
}

function inBrowseTreesMode() { return currentMode === browseTreesMode; }
function inAddTreeMode()     { return currentMode === addTreeMode; }
function inEditTreeMode()    { return currentMode === editTreeDetailsMode; }

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
        displayFields: '#sidebar-browse-trees [data-class="display"]',
        editFields: '#sidebar-browse-trees [data-class="edit"]',
        validationFields: '#sidebar-browse-trees [data-class="error"]',
        onSaveBefore: editTreeDetailsMode.onSaveBefore
    });

    prompter = statePrompter.init({
        warning: config.exitWarning,
        question: config.exitQuestion
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
        $addTreeHeaderLink: $addTreeHeaderLink,
        $exploreTreesHeaderLink: $exploreTreesHeaderLink,
        mapManager: mapManager,
        plotMarker: plotMarker,
        inMyMode: inAddTreeMode,
        $sidebar: $sidebarAddTree,
        onClose: _.partial(activateBrowseTreesMode, true),
        typeaheads: [getSpeciesTypeaheadOptions(config, "add-tree-species")],
        triggerSearchBus: triggerSearchBus,
        prompter: prompter
    });

    editTreeDetailsMode.init({
        config: config,
        mapManager: mapManager,
        inlineEditForm: form,
        plotMarker: plotMarker,
        inMyMode: inEditTreeMode,
        typeaheads: [getSpeciesTypeaheadOptions(config, "edit-tree-species")]
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
    activateAddTreeMode: activateAddTreeMode
};
