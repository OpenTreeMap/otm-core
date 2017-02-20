"use strict";

// The main "map" page has several modes -- browse trees, add a tree, and edit
// tree details. Each mode has a div in the sidebar to show its UI and a JS
// module to handle UI events. This module initializes the mode modules and
// orchestrates switching between modes.

var $                   = require('jquery'),
    _                   = require('lodash'),
    reverse             = require('reverse'),
    config              = require('treemap/lib/config.js'),
    U                   = require('treemap/lib/utility.js'),
    browseTreesMode     = require('treemap/mapPage/browseTreesMode.js'),
    addTreeMode         = require('treemap/mapPage/addTreeMode.js'),
    editTreeDetailsMode = require('treemap/mapPage/editTreeDetailsMode.js'),
    addResourceMode     = require('treemap/mapPage/addResourceMode.js'),
    inlineEditForm      = require('treemap/lib/inlineEditForm.js'),
    urlState            = require('treemap/lib/urlState.js'),
    plotMarker          = require('treemap/lib/plotMarker.js'),
    statePrompter       = require('treemap/lib/statePrompter.js'),
    stickyTitles        = require('treemap/lib/stickyTitles.js'),
    prompter,
    currentMode, currentType;

var sidebarBrowseTrees          = '#sidebar-browse-trees',
    sidebarAddTree              = '#sidebar-add-tree',
    sidebarAddResource          = '#sidebar-add-resource',
    $treeDetailAccordionSection = U.$find('#tree-detail'),
    $fullDetailsButton          = U.$find('#full-details-button'),
    $treeDetailButtonGroup      = U.$find('#map-plot-details-button'),
    $exploreMapHeaderLink       = U.$find('.navbar li.explore-map'),
    $addFeatureHeaderLink       = U.$find('.navbar li[data-feature=add_plot]');

function activateMode(mode, sidebar, safeTransition, type) {

    // each mode activator takes an argument that determines
    // whether or not to lock the prompter, or in other words,
    // whether or not activateMode should prompt the user before
    // changing modes.
    if (safeTransition === true) {
        prompter.unlock();
    }
    if ((mode !== currentMode || type !== currentType) &&
        prompter.canProceed()) {
        if (currentMode && currentMode.deactivate) {
            currentMode.deactivate();
        }
        $(sidebar).siblings().hide();
        $(sidebar).show();
        if (mode.activate) {
            mode.activate(type);
        }

        // lockOnActivate will specify whether to leave the
        // prompter in a locked state, which causes a
        // prompt on mode changes and page navigation.
        if (mode.lockOnActivate === true) {
            prompter.lock();
        } else {
            prompter.unlock();
        }
        if ('hideSearch' in mode) {
            $('body').toggleClass('hide-search', mode.hideSearch);
        }
        urlState.setModeName(mode.name);
        urlState.setModeType(type);
        currentMode = mode;
        currentType = type;
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
function activateAddResourceMode(safeTranstion, type) {
    activateMode(addResourceMode, sidebarAddResource, safeTranstion, type);
}

function inBrowseTreesMode() { return currentMode === browseTreesMode; }
function inAddTreeMode()     { return currentMode === addTreeMode; }
function inEditTreeMode()    { return currentMode === editTreeDetailsMode; }
function inAddResourceMode() { return currentMode === addResourceMode; }

function init(mapManager, triggerSearchBus, embed, completedSearchStream) {
    // browseTreesMode and editTreeDetailsMode share an inlineEditForm,
    // so initialize it here.
    var form = inlineEditForm.init({
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
    form.saveOkStream.onValue(triggerSearchBus.push);

    plotMarker.init(mapManager.map);

    browseTreesMode.init({
        map: mapManager.map,
        embed: embed,
        completedSearchStream: completedSearchStream,
        inMyMode: inBrowseTreesMode,
        $treeDetailAccordionSection: $treeDetailAccordionSection,
        $fullDetailsButton: $fullDetailsButton,
        inlineEditForm: form,
        plotMarker: plotMarker,
        $buttonGroup: $treeDetailButtonGroup
    });

    addTreeMode.init({
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
        typeahead: getSpeciesTypeaheadOptions("add-tree-species"),
        addFeatureRadioOptions: 'addFeatureOptions',
        triggerSearchBus: triggerSearchBus
    });

    editTreeDetailsMode.init({
        mapManager: mapManager,
        inlineEditForm: form,
        plotMarker: plotMarker,
        inMyMode: inEditTreeMode,
        typeaheads: [getSpeciesTypeaheadOptions("edit-tree-species")]
    });

    addResourceMode.init({
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

    // Update CSS on search options bar to keep it fixed to top of the screen
    // when scrolling on mobile
    stickyTitles($('#map-content'), '#map-plot-details-button', $('#sidebar-browse-trees'));
}

function getSpeciesTypeaheadOptions(idPrefix) {
    return {
        name: "species",
        url: reverse.species_list_view(config.instance.url_name),
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
