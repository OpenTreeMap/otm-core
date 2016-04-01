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
    R = require('ramda'),
    otmTypeahead = require('treemap/otmTypeahead'),
    U = require('treemap/utility'),
    geocoderInvokeUi = require('treemap/geocoderInvokeUi'),
    geocoderResultsUi = require('treemap/geocoderResultsUi'),
    Search = require('treemap/search'),
    udfcSearch = require('treemap/udfcSearch'),
    BU = require('treemap/baconUtils'),
    MapManager = require('treemap/MapManager'),
    mapManager = new MapManager();

var dom = {
    subheader: '.subhead',
    advanced: '.advanced-search',
    advancedToggle: '#search-advanced',
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
    speciesSearchToggle: '#species-toggle',
    speciesSearchContainer: '#species-search-wrapper'
};

// Placed onto the jquery object
require('bootstrap-datepicker');

var showGeocodeError = function (e) {
    // Bacon just returns an error string
    if (_.isString(e)) {
        // TODO: Toast
        window.alert(e);
    // If there was an error from the server the error
    // object contains standard http info
    } else if (e.status && e.status === 404) {
        // TODO: Toast
        window.alert('There were no results matching your search.');
    } else {
        // TODO: Toast
        window.alert('There was a problem running your search.');
    }
};

var getSearchDatum = function() {
    return otmTypeahead.getDatum($('#boundary-typeahead'));
};

function redirectToSearchPage(config, filters, wmCoords) {
    var getZPortion = function (wmCoords) {
            var ll = U.webMercatorToLatLng(wmCoords.x, wmCoords.y);
            return '&z='+ mapManager.ZOOM_PLOT + '/' + ll.lat + '/' + ll.lng;
        },
        query = Search.makeQueryStringFromFilters(config, filters);

    query += wmCoords ? getZPortion(wmCoords) : '';

    window.location.href = config.instance.url + 'map/?' + query;
}

function initSearchUi(config, searchStream) {
    var $advancedToggle = $(dom.advancedToggle),
        $subheader = $(dom.subheader);
    otmTypeahead.create({
        name: "species",
        url: config.instance.url + "species/",
        input: "#species-typeahead",
        template: "#species-element-template",
        hidden: "#search-species",
        button: "#species-toggle",
        reverse: "id",
        forceMatch: true
    });
    otmTypeahead.create({
        name: "boundaries",
        url: config.instance.url + "boundaries/",
        input: "#boundary-typeahead",
        template: "#boundary-element-template",
        hidden: "#boundary",
        button: "#boundary-toggle",
        reverse: "id",
        sortKeys: ['sortOrder', 'value'],
        geocoder: true,
        geocoderBbox: config.instance.extent
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

        if ($advancedToggle.hasClass('active')) {
            $advancedToggle.removeClass('active').blur();
        }
        if ($subheader.hasClass('expanded')) {
            $subheader.removeClass('expanded');
        }
        updateUi(Search.buildSearch());
    });

    $advancedToggle.on("click", function() {
        $advancedToggle.toggleClass('active').blur();
        $subheader.toggleClass('expanded');
    });
    $subheader.find("input[data-date-format]").datepicker();
}

function updateUi(search) {
    updateActiveSearchIndicators(search);
    updateDisabledFieldGroups(search);
    updateDisabledFields(search);
}

function updateActiveSearchIndicators(search) {
    var activeCategories = _(search.filter)
        .map(getFilterCategory)
        .unique()
        .filter() // remove "false" (category with a filter that isn't displayed)
        .value();

    function getFilterCategory(filter, key) {
        var moreSearchFeatureBlacklist;

        if (_.has(filter, 'ISNULL')) {
            return 'missing';
        } else {
            var featureName = key.split('.')[0],
                featureCategories = ['tree', 'plot', 'mapFeature'],
                simpleSearchKeys = ['species.id', 'mapFeature.geom'],
                displayedFeatures = _.map(search.display, R.toLower);
            if (_.contains(simpleSearchKeys, key)) {
                // do not add filter categories for search fields that are not
                // part of the advanced search.
                return false;
            } else if (_.contains(featureCategories, featureName)) {
                if (!hasDisplayFilters(search) || _.contains(displayedFeatures, featureName)) {
                    return featureName;
                } else {
                    return false; // feature filter is disabled by display filter
                }
            } else if (featureName.startsWith('udf:')) {
                return 'stewardship';
            } else {
                moreSearchFeatureBlacklist = _.union(featureCategories, ['species']);
                if (!_.contains(moreSearchFeatureBlacklist, featureName)) {
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

    $(dom.advancedToggle).toggleClass('filter-active', activeCategories.length > 0);

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
        if (_.contains(search.display, 'Plot')) {
            // Showing trees & empty plots; enable both tree & plot fields
            fieldGroupsToEnable.push('Tree');
        } else if (_.contains(search.display, 'Tree')) {
            // Showing trees & not empty plots; enable both tree & plot fields
            fieldGroupsToEnable.push('Plot');
        } else if (_.contains(search.display, 'EmptyPlot')) {
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
            minOrMax = _.contains(searchTypes, 'MIN') || _.contains(searchTypes, 'MAX');
        $(dom.searchFields).filter('[name="' + field + '"]').each(function(i, elem) {
            var $elem = $(elem),
                searchType = $elem.attr('data-search-type');

            // Min/Max fields don't affect other min/Max fields
            if (minOrMax && _.contains(['MIN', 'MAX'], searchType)) {
                return;
            }

            if (($elem.is(':checkbox') && !$elem.is(':checked')) || $elem.val().length === 0) {
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
    $(dom.speciesSearchToggle).prop('disabled', disabled);
    $(dom.speciesSearchContainer).toggleClass('disabled', disabled);
    $(dom.speciesDisabledMessage).toggle(disabled);
}

module.exports = exports = {

    initDefaults: function (config) {
        var streams = exports.init(config),
            redirect = _.partial(redirectToSearchPage, config),
            redirectWithoutLocation = _.partialRight(redirect, undefined);

        streams.filterNonGeocodeObjectStream.onValue(redirectWithoutLocation);
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

    init: function (config) {
        var searchStream = BU.enterOrClickEventStream({
                inputs: 'input[data-class="search"]',
                button: '#perform-search'
            }),
            resetStream = $("#search-reset").asEventStream("click"),
            filtersStream = searchStream
                .filter(function() {
                    var datum = getSearchDatum();
                    return !(datum && datum.magicKey);
                })
                .map(Search.buildSearch),
            uSearch = udfcSearch.init(resetStream),

            geocodeResponseStream = geocoderInvokeUi({
                config: config,
                searchTriggerStream: searchStream,
                addressInput: '#boundary-typeahead'
            }),
            geocodedLocationStream = geocoderResultsUi(
                {
                    geocodeResponseStream: geocodeResponseStream,
                    cancelGeocodeSuggestionStream: resetStream,
                    resultTemplate: '#geocode-results-template',
                    addressInput: '#boundary-typeahead',
                    displayedResults: '.search-block [data-class="geocode-result"]'
                });

        geocodeResponseStream.onError(showGeocodeError);
        initSearchUi(config, searchStream);

        return {
            // a stream events corresponding to clicks on the reset button.
            resetStream: resetStream,

            // the final, pinpointed stream of geocoded locations
            // consumers should act with this data directly to
            // modify the state of their UI or pass to other consumers.
            geocodedLocationStream: geocodedLocationStream,

            // Stream of search events, carries the filter object and display
            // list with it. should be used by consumer to execute searches.
            filterNonGeocodeObjectStream: filtersStream,

            applySearchToDom: function (search) {
                Search.applySearchToDom(search);
                uSearch.applyFilterObjectToDom(search);
                updateUi(search);
            }
        };
    }
};
