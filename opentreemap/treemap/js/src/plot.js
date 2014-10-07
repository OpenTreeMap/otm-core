"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    otmTypeahead = require('treemap/otmTypeahead'),
    BU = require('treemap/baconUtils'),
    FH = require('treemap/fieldHelpers'),
    diameterCalculator = require('treemap/diameterCalculator'),
    plotUdf = require('treemap/plotUdf'),
    moment = require('moment');

// Placed onto the jquery object
require('bootstrap-datepicker');

exports.init = function(options) {
    var form = options.form,
        $addTree = $(options.addTree),
        $noTreeMessage = $(options.noTreeMessage),
        $cancelAddTree = $(options.cancelAddTree),
        $addTreeSection = $(options.addTreeSection),
        $treeSection = $(options.treeSection);

    otmTypeahead.bulkCreate(options.typeaheads);

    $('[data-date-format]').datepicker();

    diameterCalculator({ formSelector: '#plot-form',
                         cancelStream: form.cancelStream,
                         saveOkStream: form.saveOkStream });

    plotUdf.init(form);

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
    $addTree.click(function() {
        var $editFields = $(options.inlineEditForm.editFields);
        $addTree.hide();
        $noTreeMessage.hide();
        $cancelAddTree.show();
        $treeSection.show();
        FH.getSerializableField($editFields, 'tree.plot').val(options.plotId);
    });
    $cancelAddTree.click(function() {
        var $editFields = $(options.inlineEditForm.editFields);
        $addTree.show();
        $noTreeMessage.show();
        $cancelAddTree.hide();
        $treeSection.hide();
        FH.getSerializableField($editFields, 'tree.plot').val('');
    });

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

    form.inEditModeProperty.onValue(function (inEditMode) {
        if (inEditMode) {
            showAddTree();
        } else {
            hideAddTree();
        }
    });
};
