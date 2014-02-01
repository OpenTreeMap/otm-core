"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    otmTypeahead = require('treemap/otmTypeahead'),
    inlineEditForm = require('treemap/inlineEditForm'),
    mapManager = require('treemap/mapManager'),
    BU = require('treemap/baconUtils'),
    FH = require('treemap/fieldHelpers'),
    Bacon = require('baconjs'),
    U = require('treemap/utility'),
    plotMover = require('treemap/plotMover'),
    plotDelete = require('treemap/plotDelete'),
    plotMarker = require('treemap/plotMarker'),
    statePrompter = require('treemap/statePrompter'),
    csrf = require('treemap/csrf'),
    imageUploadPanel = require('treemap/imageUploadPanel'),
    reverseGeocodeStreamAndUpdateAddressesOnForm =
        require('treemap/reverseGeocodeStreamAndUpdateAddressesOnForm'),
    streetView = require('treemap/streetView'),
    diameterCalculator = require('treemap/diameterCalculator'),
    History = require('history'),
    moment = require('moment');

// Placed onto the jquery object
require('bootstrap-datepicker');

exports.init = function(options) {
    var $addTree = $(options.addTree),
        $noTreeMessage = $(options.noTreeMessage),
        $cancelAddTree = $(options.cancelAddTree),
        $addTreeSection = $(options.addTreeSection),
        $treeSection = $(options.treeSection),
        $ecoBenefits = $(options.ecoBenefits);

    // Set up cross-site forgery protection
    $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

    otmTypeahead.bulkCreate(options.typeaheads);

    var prompter = statePrompter.init({
        warning: options.config.exitWarning,
        question: options.config.exitQuestion
    });

    // Add threaded comments "reply" links
    var commentFormTempl = $("#template-comment").html();

    $('a[data-comment-id]').click(function () {
        var $a = $(this);

        // Close other forms
        $(".comment-reply-form").remove();

        var templ = $("#template-comment").html();
        $a.closest(".comment").append(_.template(commentFormTempl, {
            parent: $a.data("comment-id"),
            classname: 'comment-reply-form'
        }));
    });

    if (options.config.loggedIn) {
        $('#comments-container').append(_.template(commentFormTempl, {
            parent: '',
            classname: 'comment-create-form'
        }));
    }

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

        var data = _.map(fields, function(field) {
            if ($(field).attr('data-moment-date-format')) {
                return moment($(field).datepicker("getDate")).format($(field).attr('data-moment-date-format'));
            } else {
                return $(field).val();
            }
        });

        $(this).closest('table').append(udfRowTemplate({
            fields: data
        }));
    });

    $('[data-date-format]').datepicker();

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


    var deleter = plotDelete.init({
        config: options.config,
        delete: options.delete,
        deleteConfirm: options.deleteConfirm,
        deleteCancel: options.deleteCancel,
        deleteConfirmationBox: options.deleteConfirmationBox,
        treeIdColumn: options.treeIdColumn
    });

    if (options.config.instance.supportsEcobenefits) {
        form.saveOkStream
            .map($ecoBenefits)
            .onValue('.load', options.updateEcoUrl);
    }

    var sidebarUpdate = form.saveOkStream.merge(imageFinishedStream);
    sidebarUpdate
        .map($(options.sidebar))
        .onValue('.load', options.updateSidebarUrl);

    var startInEditMode = options.startInEditMode;

    form.inEditModeProperty.onValue(function(inEditMode) {
        var hrefHasEdit = U.getLastUrlSegment() === 'edit';

        if (inEditMode) {
            prompter.lock();
            if (!hrefHasEdit) {
                History.replaceState(null, '', U.appendSegmentToUrl('edit'));
            }
        } else {
            prompter.unlock();
            if (hrefHasEdit) {
                History.replaceState(null, '', U.removeLastUrlSegment());
            }
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

    reverseGeocodeStreamAndUpdateAddressesOnForm(
        options.config, plotMarker.moveStream, '#plot-form');

    var currentPlotMover = plotMover.init({
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
        currentPlotMover.onSaveBefore(data);
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

    var newTreeIdStream = form.saveOkStream
            .map('.responseData.treeId')
            .filter(BU.isDefined);

    newTreeIdStream.onValue(function (val) {
        initializeTreeIdSection(val);
        $addTreeSection.hide();
    });

    function initializeTreeIdSection (id) {
        var $section = $(options.treeIdColumn);
        $section.attr('data-tree-id', id);
        $section.html('<a href="trees/' + id + '/">' + id + '</a>');
    }

    if (options.config.instance.basemap.type === 'google') {
        var $streetViewContainer = $(options.streetView);
        $streetViewContainer.show();
        var panorama = streetView.create({
            streetViewElem: $streetViewContainer[0],
            noStreetViewText: options.config.noStreetViewText,
            location: options.plotLocation.location
        });
        form.saveOkStream
            .map('.formData')
            .map(BU.getValueForKey, 'plot.geom')
            .filter(BU.isDefined)
            .onValue(panorama.update);
    }
};
