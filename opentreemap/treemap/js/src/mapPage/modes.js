"use strict";

// The main "map" page has several modes -- e.g. browse trees, add a tree, and
// edit tree details. Each mode has a div in the sidebar to show its UI and a JS
// module to handle UI events. This module initializes the mode modules and
// orchestrates switching between modes.

// Mode changes are initiated by calling one of the exported activation functions
// (e.g. activateAddTreeMode, activateBrowseTreesMode). Note that calls to these
// functions are not isolated in a single controller module due to the differing
// requirements of the code that calls them.

var $                   = require('jquery'),
    _                   = require('lodash'),
    reverse             = require('reverse'),
    config              = require('treemap/lib/config.js'),
    browseTreesMode     = require('treemap/mapPage/browseTreesMode.js'),
    drawAreaMode        = require('treemap/mapPage/drawAreaMode.js'),
    editAreaMode        = require('treemap/mapPage/editAreaMode.js'),
    addTreeMode         = require('treemap/mapPage/addTreeMode.js'),
    editTreeDetailsMode = require('treemap/mapPage/editTreeDetailsMode.js'),
    addResourceMode     = require('treemap/mapPage/addResourceMode.js'),
    inlineEditForm      = require('treemap/lib/inlineEditForm.js'),
    urlState            = require('treemap/lib/urlState.js'),
    plotMarker          = require('treemap/lib/plotMarker.js'),
    statePrompter       = require('treemap/lib/statePrompter.js'),
    stickyTitles        = require('treemap/lib/stickyTitles.js');

var sidebarBrowseTrees = '#sidebar-browse-trees',
    sidebarAddTree     = '#sidebar-add-tree',
    sidebarAddResource = '#sidebar-add-resource',
    map,
    prompter,
    currentMode,
    currentMapFeatureType;

function activateBrowseTreesMode(options) {
    activateMode(browseTreesMode, sidebarBrowseTrees, options);
}
function activateDrawAreaMode(options) {
    activateMode(drawAreaMode, sidebarBrowseTrees, options);
}
function activateEditAreaMode(options) {
    activateMode(editAreaMode, sidebarBrowseTrees, options);
}
function activateAddTreeMode(options) {
    activateMode(addTreeMode, sidebarAddTree, options);
}
function activateEditTreeDetailsMode(options) {
    activateMode(editTreeDetailsMode, sidebarBrowseTrees, options);
}
function activateAddResourceMode(options) {
    activateMode(addResourceMode, sidebarAddResource, options);
}

// All changes between modes use this function.
// It deactivates the current mode, activates the new mode, displays the
// appropriate sidebar, and manages "are you sure you want to exit" queries.

function activateMode(mode, sidebar, options) {

    if (options && options.skipPrompt) {
        // Caller knows we don't need an "are you sure" query
        // (e.g. when switching from edit trees mode to browse trees mode)
        prompter.unlock();
    }

    var mapFeatureType = options && options.mapFeatureType;
    if ((mode !== currentMode || mapFeatureType !== currentMapFeatureType) &&
        prompter.canProceed()) {

        if (currentMode && currentMode.deactivate) {
            currentMode.deactivate(options);
        }
        if (mode.activate) {
            mode.activate(options);
        }
        currentMode = mode;
        currentMapFeatureType = mapFeatureType;

        $(sidebar).siblings().hide();
        $(sidebar).show();

        if (mode.lockOnActivate === true) {
            prompter.lock();  // Ask "are you sure" when leaving mode
        } else {
            prompter.unlock();  // Don't ask "are you sure" when leaving mode
        }

        // On mobile we hide the search bar in some modes
        if ('hideSearch' in mode) {
            $('body').toggleClass('hide-search', mode.hideSearch);
        }
        // On mobile some transitions change the size of the map
        map.invalidateSize();
    }
}

function inBrowseTreesMode() { return currentMode === browseTreesMode; }
function inAddTreeMode()     { return currentMode === addTreeMode; }
function inEditTreeMode()    { return currentMode === editTreeDetailsMode; }
function inAddResourceMode() { return currentMode === addResourceMode; }

function init(mapManager, triggerSearchBus, embed, completedSearchStream) {
    map = mapManager.map;

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
            activateEditTreeDetailsMode({keepSelection: true});
        } else {
            activateBrowseTreesMode({
                keepSelection: true,
                skipPrompt: true
            });
        }
    });
    form.saveOkStream.onValue(triggerSearchBus.push);

    plotMarker.init(map);

    browseTreesMode.init({
        map: map,
        embed: embed,
        completedSearchStream: completedSearchStream,
        inMyMode: inBrowseTreesMode,
        inlineEditForm: form
    });

    // As discussed in http://stackoverflow.com/a/21424911, using "this" could
    // fail if modes.init() were called within this file. But it won't be, so
    // silence JSHint's warning.
    /*jshint validthis: true */

    drawAreaMode.init({
        map: map,
        modes: this,
        tooltipStrings: config.trans.tooltipsForDrawArea
    });

    editAreaMode.init({
        map: map,
        modes: this,
        tooltipStrings: config.trans.tooltipForEditArea
    });

    addTreeMode.init({
        mapManager: mapManager,
        activateBrowseTreesMode: activateBrowseTreesMode,
        inMyMode: inAddTreeMode,
        sidebar: sidebarAddTree,
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
        inMyMode: inEditTreeMode,
        typeaheads: [getSpeciesTypeaheadOptions("edit-tree-species")]
    });

    addResourceMode.init({
        mapManager: mapManager,
        activateBrowseTreesMode: activateBrowseTreesMode,
        inMyMode: inAddResourceMode,
        sidebar: sidebarAddResource,
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
    activateDrawAreaMode: activateDrawAreaMode,
    activateEditAreaMode: activateEditAreaMode,
    activateAddTreeMode: activateAddTreeMode,
    activateAddResourceMode: activateAddResourceMode
};
