"use strict";

// Given a set of search input elements (text boxes) and a "search" button,
// Return a stream of "search" events triggered by hitting "Enter" in one of
// the input boxes or clicking the "search" button.

// There are two primary methods to use this module:
// 1) call .initDefaults() with a config, which sets up basic behavior.
// 2) call .init() and use the return object to bind events to the streams.

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    otmTypeahead = require('treemap/lib/otmTypeahead.js'),
    U = require('treemap/lib/utility.js'),
    geocoderUi = require('treemap/lib/geocoderUi.js'),
    Search = require('treemap/lib/search.js'),
    udfcSearch = require('treemap/lib/udfcSearch.js'),
    MapManager = require('treemap/lib/MapManager.js'),
    reverse = require('reverse'),
    config = require('treemap/lib/config.js'),
    stickyTitles = require('treemap/lib/stickyTitles.js'),
    urlState = require('treemap/lib/urlState.js'),
    toastr = require('toastr'),
    mapManager = new MapManager();

var dom = {
    header: '.header',
    subheader: '.subhead',
    advanced: '.advanced-search',
    advancedToggle: '#search-advanced',
    resetButton: '#search-reset',
    categoryDropdown: '.advanced-search .dropdown',
    categoryToggle: '.advanced-search .dropdown-toggle',
    categoryOpenToggle: '.advanced-search .dropdown.open .dropdown-toggle',
    categoryDisplayToggle: '.advanced-search #adv-search-category-display',
    categoryContent: '.advanced-search .dropdown-menu',
    fieldGroup: '.field-group',
    fieldGroupDisabledMessage: '.fields-disabled-message',
    fieldDisabledMessage: '.field-disabled-message',
    speciesDisabledMessage: '#species-disabled',
    datePickerTextBox: '[data-date-format]',
    datePicker: '.datepicker',
    searchFields: '[data-search-type]',
    searchFieldContainer: '.search-field-wrapper',
    speciesSearchTypeahead: '#species-typeahead',
    speciesSearchContainer: '#species-search-wrapper',
    locationSearchTypeahead: '#boundary-typeahead',
    clearLocationInput: '.clear-location-input',
    foreignKey: '[data-foreign-key]'
};

// Placed onto the jquery object
require('bootstrap-datepicker');

var showGeocodeError = function (e) {
    // Bacon just returns an error string
    if (_.isString(e)) {
        toastr.error(e);
    // If there was an error from the server the error
    // object contains standard http info
    } else if (e.status && e.status === 404) {
        toastr.error('There were no results matching your search.');
    } else {
        toastr.error('There was a problem running your search.');
    }
};

var getSearchDatum = function() {
    return otmTypeahead.getDatum($(dom.locationSearchTypeahead));
};

function redirectToSearchPage(filters, latLng) {
    var query = Search.makeQueryStringFromFilters(filters);
    if (latLng) {
        query += '&z=' + mapManager.ZOOM_PLOT + '/' + latLng.lat + '/' + latLng.lng;
    }
    if (filters.address) {
        query += '&a=' + filters.address;
    }
    window.location.href = reverse.map(config.instance.url_name) + '?' + query;
}

function initSearchUi(searchStream) {
    var $advancedToggle = $(dom.advancedToggle),
        $header = $(dom.header),
        $subheader = $(dom.subheader);

    var $query_typeaheads = $('.search-right .autocomplete-group');
    $query_typeaheads.each(function () {
        var $textInput = $(this).find('[type="text"]');
        var $hiddenInput = $(this).find('[type="hidden"]');

        otmTypeahead.create({
            remote: $textInput.data('remote'),
            display: $textInput.data('display'),
            input: $textInput,
            template: '#' + $textInput.data('qualifier') + '-template',
            hidden: $hiddenInput,
            reverse: "id",
            minLength: 1
        });
    });

    // Keep dropdowns open when controls in them are clicked
    $(dom.categoryContent).on('click', stopPropagation);
    $(dom.datePickerTextBox).datepicker()
        .on('show', function(e) {
            $(dom.datePicker).on('click', stopPropagation);
        })
        .on('hide', function(e) {
            $(dom.datePicker).off('click', stopPropagation);
        });
    function stopPropagation(e) {
        e.stopPropagation();
    }

    // Without this, datepickers don't close when you click on the map
    $(dom.categoryDropdown).on('hide.bs.dropdown', function () {
        $(dom.datePickerTextBox).datepicker('hide');
    });

    // Enable/disable field groups when closing the "Display" dropdown
    $(dom.categoryDisplayToggle)
        .closest(dom.categoryDropdown)
        .on('hide.bs.dropdown', function () {
            updateDisabledFieldGroups(Search.buildSearch());
        });

    // Enable/disable fields when values change
    $(dom.searchFields).add(dom.speciesSearchTypeahead)
        .on('change typeahead:select', function () {
            updateDisabledFields(Search.buildSearch());
        });

    // Update UI when search executed
    searchStream.onValue(function () {
        // Close open categories (in case search was triggered by hitting "enter")
        $(dom.categoryOpenToggle).dropdown('toggle');

        toggleAdvanced(false);
        updateUi(Search.buildSearch());
    });

    $advancedToggle.on("click", function() {
        toggleAdvanced();
    });
    $subheader.find("input[data-date-format]").datepicker();

    function toggleAdvanced(active) {
        $advancedToggle.toggleClass('active', active).blur();
        $subheader.toggleClass('expanded', active);
        $header.toggleClass('expanded', active);
        // Waiting until we've given the browser a chance to repaint the DOM
        // to add 'collapsed' helps us prevent unwanted CSS animations
        setTimeout(function() {
            active = $header.hasClass('expanded');
            $subheader.toggleClass('collapsed', !active);
            $header.toggleClass('collapsed', !active);
        }, 20);
    }

    // Update CSS on search options bar to keep it fixed to top of the screen
    // when scrolling on mobile
    stickyTitles($('body > .wrapper'), '.search-options', $header);
}


function updateUi(search) {
    updateActiveSearchIndicators(search);
    updateDisabledFieldGroups(search);
    updateDisabledFields(search);
}

function updateActiveSearchIndicators(search) {
    var simpleSearchKeys = ['species.id', 'mapFeature.geom'],
        activeCategories = _(search.filter)
            .map(getFilterCategory)
            .uniq()
            .filter() // remove "false" (category with a filter that isn't displayed)
            .value();

    function getFilterCategory(filter, key) {
        var moreSearchFeatureBlacklist;

        if (_.has(filter, 'ISNULL')) {
            return 'missing';
        } else {
            var featureName = key.split('.')[0],
                featureCategories = ['tree', 'plot', 'mapFeature'],
                displayedFeatures = _.map(search.display, function (s) {
                    return s.toLowerCase();
                });
            if (_.includes(simpleSearchKeys, key)) {
                // do not add filter categories for search fields that are not
                // part of the advanced search.
                return false;
            } else if (_.includes(featureCategories, featureName)) {
                if (!hasDisplayFilters(search) || _.includes(displayedFeatures, featureName) || featureName === 'mapFeature') {
                    return featureName;
                } else {
                    return false; // feature filter is disabled by display filter
                }
            } else if (featureName.startsWith('udf:')) {
                return 'stewardship';
            } else {
                moreSearchFeatureBlacklist = _.union(featureCategories, ['species']);
                if (!_.includes(moreSearchFeatureBlacklist, featureName)) {
                    // as a safeguard, check that this feature is not a feature
                    // that is known to never be found in the 'more' list. This
                    // prevents future features from accidentally ending up with
                    // the 'more' category.
                    return 'more';
                } else {
                    return false;
                }
            }
        }
    }

    if (hasDisplayFilters(search)) {
        activeCategories.push('display');
    }

    var simpleSearchActive = _.some(simpleSearchKeys, _.partial(_.has, search.filter)) || $(dom.locationSearchTypeahead).val() !== "";

    $(dom.advancedToggle).toggleClass('filter-active', activeCategories.length > 0);
    $(dom.advancedToggle).toggleClass('simple-filter-active', simpleSearchActive);

    $(dom.categoryToggle).removeClass('filter-active');

    _.each(activeCategories, function (category) {
        $('#adv-search-category-' + category).addClass('filter-active');
    });
}

function hasDisplayFilters(search) {
    return _.isArray(search.display);
}

function updateDisabledFieldGroups(search) {
    if (hasDisplayFilters(search)) {
        var fieldGroupsToEnable = _.clone(search.display);
        if (_.includes(search.display, 'Plot')) {
            // Showing trees & empty plots; enable both tree & plot fields
            fieldGroupsToEnable.push('Tree');
        } else if (_.includes(search.display, 'Tree')) {
            // Showing trees & not empty plots; enable both tree & plot fields
            fieldGroupsToEnable.push('Plot');
        } else if (_.includes(search.display, 'EmptyPlot')) {
            // Showing empty plots & not trees; enable just plot fields
            _(fieldGroupsToEnable).pull('EmptyPlot').push('Plot');
        }
        $(dom.fieldGroup).addClass('disabled');
        $(dom.fieldGroupDisabledMessage).show();
        _.each(fieldGroupsToEnable, function (featureName) {
            var $group = $('#search-fields-' + featureName);
            $group.removeClass('disabled');
            $group.find(dom.fieldGroupDisabledMessage).hide();
        });
    } else {
        $(dom.fieldGroup).removeClass('disabled');
        $(dom.fieldGroupDisabledMessage).hide();
    }
}

function updateDisabledFields(search) {
    var minMax = ['MIN', 'MAX'];

    // First enable all search fields
    $(dom.searchFields).prop('disabled', false);
    $(dom.fieldDisabledMessage).hide();
    $(dom.searchFieldContainer).removeClass('disabled');
    updateDisabledSpeciesFields(false);

    // Then disable all fields which are not filled in but which have the same
    // key as another filled in field
    _.each(search.filter, function(predicate, field) {
        var searchTypes = _.keys(predicate),
            minOrMax = _.includes(searchTypes, 'MIN') || _.includes(searchTypes, 'MAX');
        $(dom.searchFields).filter('[name="' + field + '"]').each(function(i, elem) {
            var $elem = $(elem),
                searchType = $elem.attr('data-search-type');

            // Min/Max fields shouldn't disable their corresponding Max/Min field
            if (minOrMax && _.includes(['MIN', 'MAX'], searchType)) {
                return;
            }

            if (($elem.is(':checkbox') && !$elem.is(':checked')) || $elem.val() === null || $elem.val().length === 0) {
                $elem.prop('disabled', true);

                if (field === 'species.id' && searchType === 'IS') {
                    updateDisabledSpeciesFields(true);
                } else {
                    $elem.closest(dom.searchFieldContainer)
                        .addClass('disabled')
                        .find(dom.fieldDisabledMessage).show();
                }
            }
        });
    });
}

function updateDisabledSpeciesFields(disabled) {
    $(dom.speciesSearchTypeahead).prop('disabled', disabled);
    $(dom.speciesSearchContainer).toggleClass('disabled', disabled);
    $(dom.speciesDisabledMessage).toggle(disabled);
}

module.exports = exports = {

    initDefaults: function () {
        var streams = exports.init(),
            redirect = _.partial(redirectToSearchPage),
            redirectWithoutLocation = _.partialRight(redirect, undefined);

        streams.filtersStream.onValue(redirectWithoutLocation);
        streams.geocodedLocationStream.onValue(function (wmCoords) {
            // get the current state of the search dom
            var filters = Search.buildSearch();
            redirect(filters, wmCoords);
        });

        streams.resetStream.onValue(Search.reset);

        // Apply an empty search to the page to get all the UI elements into
        // the correct state
        Search.reset();
    },

    init: function (options) {

        var speciesTypeahead = otmTypeahead.create({
                name: "species",
                url: reverse.species_list_view(config.instance.url_name),
                input: "#species-typeahead",
                template: "#species-element-template",
                hidden: "#search-species",
                reverse: "id"
            }),
            locationTypeahead = otmTypeahead.create({
                name: "boundaries",
                url: reverse.boundary_list(config.instance.url_name),
                input: dom.locationSearchTypeahead,
                template: "#boundary-element-template",
                hidden: "#boundary",
                reverse: "id",
                sortKeys: ['sortOrder', 'value'],
                geocoder: true,
                geocoderBbox: config.instance.extent
            }),
            ui = geocoderUi({
                locationTypeahead: locationTypeahead,
                otherTypeaheads: speciesTypeahead,
                searchButton: '#perform-search,#location-perform-search'
            }),
            geocodedLocationStream = ui.geocodedLocationStream,
            clearLocationInputStream = $(dom.clearLocationInput)
                .asEventStream('click')
                .doAction(function () { // make sure this happens first
                    locationTypeahead.clear();
                }),
            // If we're on a page where custom area is supported,
            // we need searchStream to also produce events when
            // the geojson from the anonymous boundary representing the
            // custom area has arrived and been rendered.
            customAreaSearchEvents = (!!options && options.customAreaSearchEvents) || Bacon.never(),
            searchStream = Bacon.mergeAll(
                ui.triggerSearchStream,
                clearLocationInputStream,
                customAreaSearchEvents
            ),
            searchFiltersProp = searchStream.map(Search.buildSearch).toProperty(),
            filtersStream = searchStream
                // Filter out geocoded selections.
                // The search datum will have a different object format
                // depending on the type of location selected in the
                // typeahead box.
                .filter(function() {
                    var datum = getSearchDatum();
                    return !(datum && datum.magicKey);
                })
                .map(Search.buildSearch),
            resetStream = $(dom.resetButton)
                .asEventStream("click")
                // We must also clear the location search box to avoid
                // an inconsistent state when clicking reset after a geocode.
                .doAction(function () { locationTypeahead.clear(); }),
            uSearch = udfcSearch.init(resetStream),
            searchChangedStream = Bacon
                .mergeAll(searchStream, resetStream)
                .map(true),

            firstPageLoad = true;

        geocodedLocationStream.onError(showGeocodeError);
        initSearchUi(searchStream);

        return {
            // Stream of events corresponding to clicks on the reset button.
            resetStream: resetStream,

            // Stream of geocoded locations.
            geocodedLocationStream: geocodedLocationStream,

            // Stream of search events, carrying the filter object and display
            // list with it. Should be used by consumer to execute searches.
            filtersStream: filtersStream,

            // Current value of search filters, updated for every search event
            searchFiltersProp: searchFiltersProp,

            // Has a value on all events that change the current search
            searchChangedStream: searchChangedStream,

            // Used when the url changes, resulting in a location search change
            programmaticallyUpdatedStream: locationTypeahead.programmaticallyUpdatedStream,

            applySearchToDom: function (search) {
                Search.applySearchToDom(search);
                uSearch.applyFilterObjectToDom(search);
                updateUi(search);
                if (firstPageLoad) {
                    firstPageLoad = false;
                    if (search.address && $(dom.locationSearchTypeahead).val() == search.address) {
                        locationTypeahead.getGeocodeDatum(search.address, ui.triggerGeocode);
                    }
                }
            }
        };
    }
};
