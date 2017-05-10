"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    L = require('leaflet'),
    U = require('treemap/lib/utility.js'),
    F = require('modeling/lib/func.js'),
    numeral = require('numeral'),
    Bacon = require('baconjs'),
    BU = require('treemap/lib/baconUtils.js'),
    toastr = require('toastr'),
    template = require('modeling/lib/template.js'),
    modelingParamUI = require('modeling/lib/modelingParamUI.js'),
    plotMarker = require('treemap/lib/plotMarker.js'),
    notice = require('modeling/lib/mapNotice.js'),
    ModelingUrls = require('modeling/lib/modelingUrls.js'),
    ScenarioState = require('modeling/lib/scenarioState.js'),
    scenarioResults = require('modeling/lib/scenarioResults.js'),
    Interaction = require('modeling/lib/interaction.js'),
    Tree = require('modeling/lib/tree.js'),
    Location = require('modeling/lib/location.js');

require('leaflet-draw');

var dom = {
    map: '#map',
    sidebar: '#sidebar-scenarios',
    shadow: '#sidebar-scenarios > .shadow',
    hasUidAttribute: '[data-uid]',
    rowTreeCount: '.row .tree-count',
    addTree: '.add-tree',
    removeTree: '#single-tree-container .remove',
    removeMarkerPopup: '.marker-popup .remove',
    increaseTreeQuantity: '#single-tree-container .add',
    singleTreeContainer: '#single-tree-container',
    distributionsContainer: '#distributions-container',
    distributionRows: '#distribution-rows',
    addDistribution:'.add-distribution',
    removeDistribution: '#distributions-container .remove',
    drawArea: '.draw-area',
    selectArea: '.select-area',
    editArea: '.edit-area',
    disambiguateAreaModal: '#disambiguateArea',
    noTrees: '#no-trees',
    noDistributions: '#no-distributions',
    distributionRedrawArea: '#distribution-redraw-area',
    singleTreesCount: '.summary .tree-count .single-trees-count',
    distributionsCount: '.summary .tree-count .distributions-count',
    calculateScenario: '.calculate .btn',
    resultsModal: '#scenarioResults'
};

var templates = {
    singleTree: '#single-tree-tmpl',
    distributions: '#distributions-tmpl',
    distributionRow: '#distribution-row-tmpl',
    speciesDropdown: '#species-dropdown-tmpl',
    markerPopup: '#marker-popup-tmpl',
    polygonPopup: '#polygon-popup-tmpl',
    disambiguateArea: '#disambiguate-area-tmpl'
};

var _state = null,
    _strings = null,
    _urls = null,
    _map = null,
    _mapManager = null,
    _staticUrl = '',
    _species = null,
    _polygonFeatureGroup = new L.FeatureGroup(),
    _markerFeatureGroup = new L.FeatureGroup(),
    _interruptStream = null;

function init(options) {
    _strings = options.strings;
    _urls = new ModelingUrls(options.urls);
    _map = options.map;
    _mapManager = options.mapManager;
    _staticUrl = options.config.staticUrl;
    _species = options.species;
    _interruptStream = options.interruptStream;

    _state = new ScenarioState(_strings);

    modelingParamUI.init(_state, _species);

    _mapManager.customizeVertexIcons();

    // Draw distributions panel.
    var html = renderTemplate(templates.distributions);
    $(dom.distributionsContainer).append(html);

    _state.treeChangesProperty.onValue(redrawTrees);
    _state.locationChangesProperty.onValue(redrawMarkers);
    _state.polygonChangesProperty.onValue(redrawDistributionPolygon);

    initUiStreams();
    initMarkerPopupStreams();
    initPolygonPopupStreams();

    plotMarker.init(_map);
    plotMarker.useTreeIcon(true);

    setupCollapsiblePanel(dom.distributionRedrawArea);

    _map.addLayer(_markerFeatureGroup);
    _map.addLayer(_polygonFeatureGroup);

    _mapManager.layersControl.addOverlay(_markerFeatureGroup, _strings.TREE_MARKERS);
    _mapManager.layersControl.addOverlay(_polygonFeatureGroup, _strings.LAND_USE_DISTRIBUTION_AREA);

    // Redraw tree panel if poylgon is added or removed.
    _state.treeChangesProperty.sampledBy(
        Bacon.mergeAll(
            Bacon.fromEventTarget(_polygonFeatureGroup, 'layeradd'),
            Bacon.fromEventTarget(_polygonFeatureGroup, 'layerremove')
        )
    ).onValue(redrawTrees);

    return {
        serializedProperty: _state.serializedProperty,
        load: _.bind(_state.load, _state),
        reset: _.bind(_state.reset, _state)
    };
}

function initStream(selectors, events, parentSelector) {
    parentSelector = parentSelector || dom.sidebar;
    return $(parentSelector)
        .asEventStream(events, selectors)
        .doAction('.preventDefault');
}

function initUiStreams() {
    initStream(dom.addTree, 'click')
        .onValue(addSingleTree);

    initStream(dom.removeTree, 'click')
        .map(getRowUid)
        .onValue(_state, 'removeTreeByUid');

    initStream(dom.removeMarkerPopup, 'click', dom.map)
        .map(getRowUid)
        .onValue(_state, 'removeLocationByUid');

    _state.treeChangesProperty.sampledBy(
        initStream(dom.increaseTreeQuantity, 'click')
            .map(getRowUid),
        findTreeByUid
    ).onValue(addSingleTreeFromExisting);

    _state.treeChangesProperty.sampledBy(
            initStream('input, select', 'change', dom.singleTreeContainer)
                .map(getRowUid),
            findTreeByUid
        )
        .map(updateSingleTree)
        .onValue(_state, 'updateTree');

    initStream(dom.addDistribution, 'click')
        .onValue(addDistribution);

    initStream(dom.removeDistribution, 'click')
        .map(getRowUid)
        .onValue(_state, 'removeTreeByUid');

    _state.treeChangesProperty.sampledBy(
            initStream('input, select', 'change', dom.distributionRows)
                .map(getRowUid),
            findTreeByUid
        )
        .map(updateDistribution)
        .onValue(_state, 'updateTree');

    initStream(dom.drawArea, 'click')
        .onValue(drawArea);

    initStream(dom.selectArea, 'click')
        .onValue(selectArea);

    initStream(dom.editArea, 'click', 'body')
        .onValue(editArea);

    Bacon.combineTemplate({
            scenario: _state.serializedProperty,
            validationErrors: _state.validationErrorsProperty
        })
        .sampledBy(initStream(dom.calculateScenario, 'click'))
        .onValue(calculateScenario);
}

function initMarkerPopupStreams() {
    var popupOpenStream =
            Bacon.fromEventTarget(_markerFeatureGroup, 'popupopen'),
        popupClosedStream =
            Bacon.fromEventTarget(_markerFeatureGroup, 'popupclose');

    var locationForCurrentPopup =
        _state.locationChangesProperty.sampledBy(
            popupOpenStream.map('.layer.uid'),
            findLocationByUid
        );

    var treeForCurrentPopup =
        _state.treeChangesProperty.sampledBy(
            locationForCurrentPopup.map('.treeUid'),
            findTreeByUid
        );

    var renderPopupContent = function(loc, popup, tree) {
        var species = _.find(_species, {otm_code: tree.species()}),
            html = renderTemplate(templates.markerPopup, {
                tree: tree,
                loc: loc,
                speciesName: species && species.common_name
            });
        popup.setContent(html);
    };

    // Return a stream that will emit a signal when the popup is closed
    // or the relevant tree has been deleted.
    var getPopupClosedStream = function(loc) {
        return Bacon.mergeAll(
            popupClosedStream,
            _state.locationRemovedStream.filter(function(uid) {
                return loc.uid() === uid;
            })
        );
    };

    var updatePopupWhenTreeChages = function(loc, popup, tree) {
        _state.treeUpdatedStream
            .takeUntil(getPopupClosedStream(loc))
            .filter(function(other) {
                return tree.uid() === other.uid();
            })
            .onValue(renderPopupContent, loc, popup);
    };

    Bacon.zipAsArray(
        locationForCurrentPopup,
        popupOpenStream.map('.popup'),
        treeForCurrentPopup
    ).onValues(function(loc, popup, tree) {
        renderPopupContent(loc, popup, tree);
        updatePopupWhenTreeChages(loc, popup, tree);
    });
}

function initPolygonPopupStreams() {
    _state.polygonChangesProperty.onValue(function() {
        var poly = _polygonFeatureGroup.getLayers()[0];
        if (poly) {
            var area = U.getPolygonDisplayArea(poly),
                displayArea = numeral(area).format('0,0') + ' ' + _strings.SQ_FT,
                html = renderTemplate(templates.polygonPopup, {
                    displayArea: displayArea
                });
            _polygonFeatureGroup.bindPopup(html);
        }
    });
}

function show() {
    $(dom.sidebar).removeClass('hidden');
}

function hide() {
    $(dom.sidebar).addClass('hidden');
}

function enableSidebar() {
    $(dom.shadow).addClass('hidden');
}

function disableSidebar() {
    $(dom.shadow).removeClass('hidden');
}

function findTreeByUid(trees, uid) {
    return _.find(trees, function(tree) {
        return tree.uid() === uid;
    });
}

function findLocationByUid(locations, uid) {
    return _.find(locations, function(loc) {
        return loc.uid() === uid;
    });
}

// TODO: debounce
function redrawTrees(trees) {
    var groupedTrees = _.groupBy(trees, function(tree) {
        return tree.type();
    });

    // Draw individual trees.
    $(dom.singleTreeContainer).children().remove();
    _.each(groupedTrees.single, function(tree) {
        var html = renderTemplate(templates.singleTree, {
            tree: tree
        });
        $(dom.singleTreeContainer).append(html);
    });

    // Draw distributions.
    $(dom.distributionRows).children().remove();
    _.each(groupedTrees.distribution, function(tree) {
        var html = renderTemplate(templates.distributionRow, {
            tree: tree
        });
        $(dom.distributionRows).append(html);
    });

    // Update panel visibility and tree counts.
    var tally = _.reduce(trees, function(acc, tree) {
        acc[tree.type()] += tree.quantity();
        return acc;
    }, {single: 0, distribution: 0});

    $(dom.noTrees).toggleClass('hidden', tally.single > 0);

    if (polygonExists()) {
        $(dom.noDistributions).addClass('hidden');
        $(dom.distributionRedrawArea).removeClass('hidden');
    } else {
        $(dom.noDistributions)
            .toggleClass('hidden', tally.distribution > 0);
        $(dom.distributionRedrawArea)
            .toggleClass('hidden', tally.distribution === 0);
    }

    $(dom.singleTreesCount).html(
        tally.single === 1 ? _strings.ONE_TREE
        : tally.single + ' ' + _strings.TREES
    );

    $(dom.distributionsCount).html(
        tally.distribution === 1 ? _strings.ONE_TREE
        : tally.distribution + ' ' + _strings.TREES
    );
}

// TODO: debounce
function redrawMarkers(locations) {
    _markerFeatureGroup.clearLayers();
    _.each(locations, function(loc) {
        var marker = createMarker(new L.LatLng(loc.lat(), loc.lng()));
        marker.uid = F.getter(loc.uid());
        marker.addTo(_markerFeatureGroup);
        Bacon.fromEventTarget(marker, 'dragend')
            .takeUntil(Bacon.fromEventTarget(marker, 'remove'))
            .map(marker, 'getLatLng')
            .map(function(latlng) {
                return loc.clone({
                    lat: latlng.lat,
                    lng: latlng.lng
                });
            })
            .onValue(_state, 'updateLocation');
    });
}

function redrawDistributionPolygon(polygonJSON) {
    var geojson = new L.GeoJSON(polygonJSON);
    _polygonFeatureGroup.clearLayers();
    _.each(geojson.getLayers(), function(layer) {
        _polygonFeatureGroup.addLayer(layer);
    });
}

function addSingleTree() {
    var completeStream = placeMarker(_strings.PROMPT_PLACE_TREE);
    completeStream.onValue(function(latlng) {
        var tree = new Tree({
            type: 'single',
            species: getDefaultSpecies(_species)
        });
        _state.addTree(tree);
        _state.addLocation(new Location({
            treeUid: tree.uid(),
            lat: latlng.lat,
            lng: latlng.lng
        }));
    });
}

function addSingleTreeFromExisting(tree) {
    var completeStream = placeMarker(_strings.PROMPT_CLONE_TREE)
        .map(function(latlng) {
            return new Location({
                treeUid: tree.uid(),
                lat: latlng.lat,
                lng: latlng.lng
            });
        });
    completeStream.onValue(_state, 'addLocation');
}

function updateSingleTree(tree) {
    var $row = findRowByUid(tree.uid()),
        species = $row.find('.species').val(),
        diameter = getDiameter($row);
    return tree.clone({
        diameter: diameter,
        species: species
    });
}

function addDistribution() {
    // Draw polygon if it doesn't exist.
    var completeStream = polygonExists() ?
            Bacon.once() :
            drawArea();

    completeStream.onValue(function() {
        var tree = new Tree({
            type: 'distribution',
            species: getDefaultSpecies(_species)
        });
        _state.addTree(tree);
    });
}

function updateDistribution(tree) {
    var $row = findRowByUid(tree.uid()),
        species = $row.find('.species').val(),
        diameter = getDiameter($row),
        quantity = parseInt($row.find('.quantity').val(), 10);
    if (quantity > 5000) {
        quantity = 5000;
    } else if (quantity < 1 || isNaN(quantity)) {
        quantity = 1;
    }
    return tree.clone({
        diameter: diameter,
        species: species,
        quantity: quantity
    });
}

function getDiameter($row) {
    var value = $row.find('.diameter').val(),
        result = parseFloat(value),
        defaultDiameter = 2;
    return isFinite(result) && result > 0 ? result : defaultDiameter;
}

// Return UID for DOM element targeted by a jQuery event.
function getRowUid(jQueryEvent) {
    var $row = $(jQueryEvent.target).parents(dom.hasUidAttribute);
    return $row.data('uid');
}

// Return DOM element for a UID.
function findRowByUid(uid) {
    return $('[data-uid=' + uid + ']', dom.sidebar);
}

function polygonExists() {
    return _polygonFeatureGroup.getLayers().length > 0;
}

// Draw polygon then add it to the map, unless it was canceled.
function drawArea() {
    var interaction = new Interaction(),
        newPolygonStream = Bacon.fromEventTarget(_map, 'draw:created')
            .takeWhile(interaction.inProgress)
            .map('.layer'),
        drawer = new L.Draw.Polygon(_map, {showArea: true});

    drawer.enable();
    managePolygonCreation(
        interaction, newPolygonStream, _strings.PROMPT_DRAW_AREA);

    interaction.onEnd(function() {
        drawer.disable();
    });

    return newPolygonStream;
}

function managePolygonCreation(interaction, newPolygonStream, message) {
    _map.removeLayer(_polygonFeatureGroup);

    var noticeStreams = notice.show(message, interaction);

    noticeStreams.cancel
        .takeWhile(interaction.inProgress)
        .onValue(interaction, 'stop');

    _map.closePopup();
    disableSidebar();

    newPolygonStream.onValue(function (newPolygonLayer) {
        _polygonFeatureGroup.clearLayers();
        _polygonFeatureGroup.addLayer(newPolygonLayer);
        _state.updatePolygon(_polygonFeatureGroup.toGeoJSON());
        interaction.stop();
    });

    _interruptStream
        .takeWhile(interaction.inProgress)
        .onValue(interaction, 'stop');

    interaction.onEnd(function() {
        enableSidebar();
        _map.addLayer(_polygonFeatureGroup);
    });
}

function selectArea() {
    var interaction = new Interaction(),
        newPolygonStream = Bacon.fromEventTarget(_map, 'click')
            .takeWhile(interaction.inProgress)
            .map(getLatLng)
            .flatMap(BU.jsonRequest('GET', _urls.boundariesAtPointUrl()))
            .flatMap(disambiguateAreas)
            .filter('.geom') // ignore clicks that missed all areas
            .map(function(area) {
                    var geoJson = JSON.parse(area.geom),
                        layerGroup = L.geoJson(geoJson),
                        layer = layerGroup.getLayers()[0];
                    return layer;
                });

    managePolygonCreation(
        interaction, newPolygonStream, _strings.PROMPT_SELECT_AREA);
}

function getLatLng(e) {
    return {lat: e.latlng.lat, lng: e.latlng.lng};
}

function disambiguateAreas(areas) {
    if (areas.length === 0) {
        toastr.options = {
            "positionClass": "toast-bottom-right",
            "timeOut": "3000"
        };
        toastr.warning(_strings.WARNING_NO_AREAS);
        return false;

    } else if (areas.length === 1) {
        return areas[0];

    } else {
        var html = renderTemplate(templates.disambiguateArea, {areas: areas}),
            $panel = $(dom.disambiguateAreaModal);
        $panel.find('.modal-body').html(html);
        $panel.modal('show');
        var chosenAreaStream = $panel.find('a')
                .asEventStream('click')
                .map(function (e) {
                    $panel.modal('hide');
                    var index = $(e.target).data('index');
                    return areas[index];
                });
        return chosenAreaStream;
    }
}

function editArea() {
    var interaction = new Interaction(),
        editor = new L.EditToolbar.Edit(_map, {
            featureGroup: _polygonFeatureGroup
        }),
        noticeStreams = notice.show(
            _strings.PROMPT_EDIT_AREA, interaction, ['cancel', 'done']);

    _map.closePopup();
    disableSidebar();
    editor.enable();

    noticeStreams.cancel
        .takeWhile(interaction.inProgress)
        .onValue(function() {
            editor.revertLayers();
            interaction.stop();
        });

    noticeStreams.done
        .takeWhile(interaction.inProgress)
        .onValue(function() {
            editor.save();
            _state.updatePolygon(_polygonFeatureGroup.toGeoJSON());
            interaction.stop();
        });

    _interruptStream
        .takeWhile(interaction.inProgress)
        .onValue(interaction, 'stop');

    interaction.onEnd(function() {
        editor.disable();
        enableSidebar();
    });
}

function calculateScenario(data) {
    var $calculateScenario = $(dom.calculateScenario),
        hasErrors = data.validationErrors && data.validationErrors.length;
    if (hasErrors) {
        displayValidationErrors(data.validationErrors);
        return;
    }
    $calculateScenario.prop('disabled', true);
    scenarioResults.clear();

    var resultsStream = BU.jsonRequest(
            'POST', _urls.calculateScenarioUrl())(data.scenario);

    resultsStream.onError(function (xhr) {
        $calculateScenario.prop('disabled', false);
        toastr.error(_strings.CALCULATE_SCENARIO_UNKNOWN_ERROR);
    });

    resultsStream.onValue(function (results) {
        $(dom.resultsModal)
            .modal('show')  // can't set chart sizes until modal visible
            .off('shown.bs.modal')
            .on('shown.bs.modal', function () {
                $calculateScenario.prop('disabled', false);
                scenarioResults.show(data.scenario.name, results);
            });
    });
}

// Return a stream that will emit a LatLng if the user successfully
// placed a map marker.
function placeMarker(message) {
    var interaction = new Interaction(),
        completeStream = plotMarker.moveStream
            .takeWhile(interaction.inProgress);

    var noticeStreams = notice.show(message, interaction);

    noticeStreams.cancel
        .takeWhile(interaction.inProgress)
        .onValue(interaction, 'stop');

    _map.closePopup();
    disableSidebar();
    plotMarker.enablePlacing();

    completeStream.onValue(interaction, 'stop');

    _interruptStream
        .takeWhile(interaction.inProgress)
        .onValue(interaction, 'stop');

    interaction.onEnd(function() {
        plotMarker.disablePlacing();
        plotMarker.hide();
        enableSidebar();
    });

    return completeStream;
}

function createMarker(latlng) {
    var url = _staticUrl + 'img/mapmarker_viewmode.png',
        marker = new L.Marker(latlng, {
            draggable: true,
            icon: new L.Icon({
                iconUrl: url,
                iconSize: [78, 75],
                iconAnchor: [36, 62]
            })
        });
    // The 'popupopen' even won't fire unless you bind an empty popup.
    marker.bindPopup('', {
        offset: new L.Point(0, -52)
    });
    return marker;
}

function renderTemplate(tmplName, bindings) {
    var helpers = {
            renderSpeciesDropdown: renderSpeciesDropdown
        };
    bindings = _.defaults({}, bindings, helpers);
    return template.render(tmplName, bindings);
}

function renderSpeciesDropdown(selected_value) {
    return template.render(templates.speciesDropdown, {
        all_species: _species,
        selected: selected_value
    });
}

var getDefaultSpecies = _.memoize(function(species) {
    var priority = [
            function(s) { return (/red maple/i).test(s.common_name); },
            function(s) { return (/maple/i).test(s.common_name); }
        ];
    var result =
        _.map(species, function(s) {
            return _.map(priority, function(criteria, i) {
                return {
                    score: i,
                    otm_code: s.otm_code,
                    match: criteria(s)
                };
            });
        });
    result = _.flattenDeep(result);
    result = _.filter(result, 'match');
    result = _.orderBy(result, 'score');
    return result.length > 0 ? result[0].otm_code : null;
});

function setupCollapsiblePanel(targetSelector) {
    initStream('.collapsible-header a', 'click', targetSelector)
        .map($(targetSelector)
            .find('.collapsible-body, .notch-expanded, .notch-collapsed'))
        .onValue('.toggleClass', 'hidden');
}

function displayValidationErrors(validationErrors) {
    var groupedErrors = _.groupBy(validationErrors, 'message');
    _.each(groupedErrors, function(errors, message) {
        // Display toastr alert.
        var errorLevel = _.head(errors).level || 'error';
        if (errorLevel === 'error') {
            toastr.error(message);
        } else if (errorLevel === 'warning') {
            toastr.warning(message);
        }

        // Highlight form fields.
        _.each(
            _.filter(_.flatten(_.map(errors, findValidationErrorField))),
            function($el) {
                $el.addClass('has-error');
            }
        );
    });
}

// Return 1 or more form fields relevant for validation error.
function findValidationErrorField(e) {
    if (e.type === 'tree') {
        var $row = findRowByUid(e.uid);
        if (e.field === 'diameter') {
            return $row.find('.diameter').parent();
        }
        if (e.field === 'quantity') {
            return $row.find('.quantity').parent();
        }
    }
    return null;
}

module.exports = {
    init: init,
    show: show,
    hide: hide
};
