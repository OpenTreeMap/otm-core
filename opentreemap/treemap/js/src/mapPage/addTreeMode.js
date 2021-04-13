"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    BU = require('treemap/lib/baconUtils.js'),
    _ = require('lodash'),
    FH = require('treemap/lib/fieldHelpers.js'),
    U = require('treemap/lib/utility.js'),
    reverse = require('reverse'),
    addMapFeature = require('treemap/mapPage/addMapFeature.js'),
    mapFeatureUdf = require('treemap/lib/mapFeatureUdf.js'),
    otmTypeahead = require('treemap/lib/otmTypeahead.js'),
    plotMarker = require('treemap/lib/plotMarker.js'),
    uploadPanel = require('treemap/lib/uploadPanelAddTreePhoto.js'),
    diameterCalculator = require('treemap/lib/diameterCalculator.js'),
    config = require('treemap/lib/config.js');

var activateMode = _.identity,
    deactivateMode = _.identity,
    STEP_LOCATE = 0,
    STEP_DETAILS = 1,
    STEP_FINAL = 2;

function init(options) {
    var mapFeatureBus = new Bacon.Bus();
    options.addMapFeatureBus = mapFeatureBus;
    var $sidebar = $(options.sidebar),
        $speciesTypeahead = U.$find('#add-tree-species-typeahead', $sidebar),
        $summaryHead = U.$find('.summaryHead', $sidebar),
        $isEmptySite = U.$find('#is-empty-site', $sidebar),
        $summarySubhead = U.$find('.summarySubhead', $sidebar),
        typeahead = otmTypeahead.create(options.typeahead),

        clearEditControls = function() {
            typeahead.clear();
        },
        manager = addMapFeature.init(
            _.extend({
                clearEditControls: clearEditControls,
                onSaveBefore: onSaveBefore}, options)
        );

    activateMode = function() {
        manager.activate();
        // Let user start creating a feature (by clicking the map)
        plotMarker.useTreeIcon(true);
        plotMarker.enablePlacing();
        $('body').addClass('add-feature');

        // this is a hard reset on these fields
        $('#empty-site-photos').hide();
        $('#tree-photos').show();
        $isEmptySite.prop('checked', false);
    };

    deactivateMode = function() {
        typeahead.clear();
        manager.deactivate();
    };

    var shapeImageFinishedStream = uploadPanel.init({
        panelId: '#shape-photo-upload',
        dataType: 'html',
        addMapFeatureBus: mapFeatureBus
    });

    var barkImageFinishedStream = uploadPanel.init({
        panelId: '#bark-photo-upload',
        dataType: 'html',
        addMapFeatureBus: mapFeatureBus
    });

    var leafImageFinishedStream = uploadPanel.init({
        panelId: '#leaf-photo-upload',
        dataType: 'html',
        addMapFeatureBus: mapFeatureBus
    });

    var emptySiteImageFinishedStream = uploadPanel.init({
        panelId: '#empty-site-photo-upload',
        dataType: 'html',
        addMapFeatureBus: mapFeatureBus
    });
    // if we just mapped an empty site, then redo the photoUpload stream
    // in case we partially mapped this
    emptySiteImageFinishedStream.onValue(function(value) {
        photoUploads = Bacon.combineAsArray(
            shapeImageFinishedStream,
            barkImageFinishedStream,
            leafImageFinishedStream
        );

        photoUploads.onValue(function(value){
            photoUploads()
            photoUploads = Bacon.combineAsArray(
                shapeImageFinishedStream,
                barkImageFinishedStream,
                leafImageFinishedStream
            );
        });
    });

    var photoUploads = Bacon.combineAsArray(
        shapeImageFinishedStream,
        barkImageFinishedStream,
        leafImageFinishedStream
    );
    var photoUploadSubscription = photoUploads.onValue(function(value){
        if (value.length != 3 || !value.every(x => x['tree_id'] == value[0]['tree_id']))
            return;

        var treeId = value[0]['tree_id'];

        var url = reverse.Urls.inaturalist_create_observation_for_tree({
            instance_url_name: config.instance.url_name,
            tree_id: treeId
        });

        var stream = BU.jsonRequest('POST', url)();
        stream.onValue(function() {console.log('submitted to iNat'); });
    });

    // start off hidden
    $('#empty-site-photos').hide();
    $isEmptySite.on('change', function() {
        if(this.checked){
            $('#empty-site-photos').show();
            $('#tree-photos').hide();
        } else {
            $('#empty-site-photos').hide();
            $('#tree-photos').show();
        }
    });

    mapFeatureUdf.init(null);

    diameterCalculator({ formSelector: options.formSelector,
                         cancelStream: manager.deactivateStream,
                         saveOkStream: manager.addFeatureStream });

    manager.stepControls.stepChangeStartStream.onValue(function (stepNumber) {
        if (stepNumber === STEP_FINAL) {
            var species = $speciesTypeahead.data('datum'),
                common_name = species ? species.common_name :
                              aTreeFieldIsSet() ? "Missing species" : "Empty planting site",
                scientific_name = species ? species.scientific_name : '';
            $summaryHead.text(common_name);
            $summarySubhead.text(scientific_name);
        }
    });

    function aTreeFieldIsSet() {
        var data = manager.getFormData();
        var treeValueSet = _.some(data, function (value, key) {
            return key && key.indexOf('tree') === 0 && value && value !== "";
        });

        // either we have a tree value set, or we have not explicitly
        // said this is an empty site
        return treeValueSet || !$isEmptySite.is(":checked");
    }

    /// This is for the Stewardship
    // By default collection udfs have their input row
    // hidden, so show that row
    $("table[data-udf-id] .editrow").css('display', '');
    // The header row may also be hidden if there are no
    // items so show that as well
    $("table[data-udf-id] .headerrow").css('display', '');
    $("table[data-udf-id] .placeholder").css('display', 'none');

    // we also always want to show the indicator
    $('span.required-indicator').html('* ');

    // before we save the data, grab any UDF data, such s Stewardship
    function onSaveBefore(data) {
        // Extract data for all rows of the collection,
        // whether entered in this session or pre-existing.
        $('table[data-udf-name]').map(function() {
            var $table = $(this);
            var name = $table.data('udf-name');

            var headers = $table.find('tr.headerrow th')
                    .map(function() {
                        return $(this).html();
                    });

            headers = _.compact(headers);

            data[name] =
                _.map($table.find('tr[data-value-id]').toArray(), function(row) {
                    var $row = $(row),
                        $tds = $row.find('td'),
                        id = $row.attr('data-value-id'),

                        rowData = _.zipObject(headers, $tds
                                    .map(function() {
                                        return $.trim($(this).attr('data-value'));
                                    }));
                    if (! _.isEmpty(id)) {
                        rowData.id = id;
                    }
                    return rowData;
                });
        });
        return data;
    }

    // In case we're adding another tree, make user move the marker
    manager.addFeatureStream.onValue(manager.requireMarkerDrag);
}

function activate() {
    activateMode();
}

function deactivate() {
    deactivateMode();
}

module.exports = {
    name: 'addTree',
    hideSearch: true,
    init: init,
    activate: activate,
    deactivate: deactivate,
    lockOnActivate: true
};
