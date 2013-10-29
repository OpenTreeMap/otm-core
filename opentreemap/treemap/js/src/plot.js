"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    otmTypeahead = require('treemap/otmTypeahead'),
    inlineEditForm = require('treemap/inlineEditForm'),
    mapManager = require('treemap/mapManager'),
    BU = require('treemap/baconUtils'),
    FH = require('treemap/fieldHelpers'),
    Bacon = require('baconjs'),
    U = require('treemap/utility'),
    plotMover = require('treemap/plotMover'),
    plotMarker = require('treemap/plotMarker'),
    csrf = require('treemap/csrf'),
    imageUploadPanel = require('treemap/imageUploadPanel'),
    streetView = require('treemap/streetView'),
    diameterCalculator = require('treemap/diameterCalculator');

exports.init = function(options) {
    var $addTree = $(options.addTree),
        $noTreeMessage = $(options.noTreeMessage),
        $cancelAddTree = $(options.cancelAddTree),
        $addTreeSection = $(options.addTreeSection),
        $treeSection = $(options.treeSection);

    // Set up cross-site forgery protection
    $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

    _.each(options.typeaheads, function(typeahead) {
        otmTypeahead.create(typeahead);
    });

    var udfRowTemplate = _.template(
        '<tr data-value-id="">' +
            '<% _.each(fields, function (field) { %>' +
            '<td> <%= field %> </td>' +
            '<% }) %>' +
            '</tr>');

    // Wire up collection udfs
    $('a[data-udf-id]').click(function() {
        var id = $(this).data('udf-id');
        var fields = $('table[data-udf-id="' + id + '"] * [data-field-name]').toArray();

        var data = _.map(fields, function(field) { return $(field).val(); });

        $(this).closest('table').append(udfRowTemplate({
            fields: data
        }));
    });

    var imageFinishedStream = imageUploadPanel.init(options.imageUploadPanel);

    var shouldBeInEditModeBus = new Bacon.Bus();
    var shouldBeInEditModeStream = shouldBeInEditModeBus.merge(
        $(window).asEventStream('popstate')
            .map(function() { return U.getLastUrlSegment() === 'edit'; }));

    var form = inlineEditForm.init(
            _.extend(options.inlineEditForm,
                     { config: options.config,
                       onSaveBefore: onSaveBefore,
                       shouldBeInEditModeStream: shouldBeInEditModeStream }));

    form.saveOkStream
        .map($(options.ecoBenefits))
        .onValue('.load', options.updatEcoUrl);

    var sidebarUpdate = form.saveOkStream.merge(imageFinishedStream);
    sidebarUpdate
        .map($(options.sidebar))
        .onValue('.load', options.updateSidebarUrl);

    var startInEditMode = options.startInEditMode;

    form.inEditModeProperty.onValue(function(inEditMode) {
        var hrefHasEdit = U.getLastUrlSegment() === 'edit';

        if (inEditMode && !hrefHasEdit) {
            U.pushState(U.appendSegmentToUrl('edit'));
        } else if (!inEditMode && hrefHasEdit) {
            U.pushState(U.removeLastUrlSegment());
        }
    });

    if (startInEditMode) {
        if (options.config.loggedIn) {
            shouldBeInEditModeBus.push(true);
            showAddTree();
        } else {
            window.location = options.config.loginUrl + window.location.href;
        }
    }

    mapManager.init({
        config: options.config,
        selector: '#map',
        disableScrollWithMouseWheel: true,
        center: options.plotLocation.location,
        zoom: mapManager.ZOOM_PLOT
    });

    plotMarker.init(options.config, mapManager.map);

    plotMover.init({
        mapManager: mapManager,
        plotMarker: plotMarker,
        inlineEditForm: form,
        editLocationButton: options.plotLocation.edit,
        cancelEditLocationButton: options.plotLocation.cancel,
        location: options.plotLocation.location
    });

    diameterCalculator({ formSelector: '#plot-form',
                         cancelStream: form.cancelStream,
                         saveOkStream: form.saveOkStream });

    function onSaveBefore(data) {
        plotMover.onSaveBefore(data);
    }

    function showAddTree() {
        $addTree.show();
        $noTreeMessage.show();
        $cancelAddTree.hide();
    }
    function hideAddTree() {
        $addTree.hide();
        $noTreeMessage.hide();
        $cancelAddTree.hide();
    }
    $(options.inlineEditForm.edit).click(showAddTree);
    $(options.inlineEditForm.cancel).click(hideAddTree);
    $addTree.click(function() {
        var $editFields = $(options.inlineEditForm.editFields),
            plotId = FH.getSerializableField($editFields, 'plot.id').val();
        $addTree.hide();
        $noTreeMessage.hide();
        $cancelAddTree.show();
        $treeSection.show();
        FH.getSerializableField($editFields, 'tree.plot').val(plotId);
    });
    $cancelAddTree.click(function() {
        var $editFields = $(options.inlineEditForm.editFields);
        $addTree.show();
        $noTreeMessage.show();
        $cancelAddTree.hide();
        $treeSection.hide();
        FH.getSerializableField($editFields, 'tree.plot').val('');
    });
    form.saveOkStream.onValue(hideAddTree);
    form.saveOkStream
        .map('.formData')
        .map(BU.getValueForKey, 'tree.plot')
        .filter(BU.isDefined)
        .onValue(_.bind($addTreeSection.hide, $addTreeSection));

    if (options.config.instance.basemap.type === 'google') {
        var $streetViewContainer = $(options.streetView);
        $streetViewContainer.show();
        var panorama = streetView.create({
            streetViewElem: $streetViewContainer[0],
            noStreetViewText: options.noStreetViewText,
            location: options.plotLocation.location
        });
        form.saveOkStream
            .map('.formData')
            .map(BU.getValueForKey, 'plot.geom')
            .filter(BU.isDefined)
            .onValue(panorama.update);
    }
};
