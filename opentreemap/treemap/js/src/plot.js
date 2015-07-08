"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    U = require('treemap/utility'),
    R = require('ramda'),
    format = require('util').format,
    otmTypeahead = require('treemap/otmTypeahead'),
    FH = require('treemap/fieldHelpers'),
    mapFeatureDelete = require('treemap/mapFeatureDelete'),
    diameterCalculator = require('treemap/diameterCalculator'),
    mapFeatureUdf = require('treemap/mapFeatureUdf'),
    plotAddTree = require('treemap/plotAddTree'),
    moment = require('moment');

// Placed onto the jquery object
require('bootstrap-datepicker');

function excludeNullMap (obs, fn) {
    return obs.map(fn)
        .filter(R.not(_.isUndefined))
        .filter(R.not(_.isNull));
}

exports.init = function(options) {
    var form = options.form,
        $treeSection = $(options.treeSection),
        newTreeIdStream = excludeNullMap(form.saveOkStream,
                                         '.responseData.treeId'),
        newTitleStream = excludeNullMap(form.saveOkStream,
                                        '.responseData.feature.title'),
        newAddressStream = excludeNullMap(form.saveOkStream,
                                          '.responseData.feature.address_full'),

        getPlotUrlFromTreeUrl = _.compose(U.removeLastUrlSegment,
                                          U.removeLastUrlSegment);


    // tree id is the sole datapoint used to determine the state
    // of the plot to be acted upon.
    // this *must be calculated dynamically* to handle the case
    // in which a tree is added and then deleted without a
    // page refresh in between.
    // this information is used for:
    // * deciding which warning message to show
    // * The url to post a delete verb to
    // * the url to redirect to
    function getTreeId() {
        return $(options.treeIdColumn).attr('data-tree-id');
    }

    function getUrls() {
        var deleteUrl = document.URL,
            afterDeleteUrl = options.config.instance.mapUrl,
            currentlyOnTreeUrl = _.contains(U.getUrlSegments(document.URL), "trees");

        if (getTreeId() !== '' && currentlyOnTreeUrl) {
            afterDeleteUrl = getPlotUrlFromTreeUrl(document.URL);
        } else if (getTreeId() !== '') {
            deleteUrl = 'trees/' + getTreeId() + '/';
            afterDeleteUrl = document.URL;
        }
        return {deleteUrl: deleteUrl,
                afterDeleteUrl: afterDeleteUrl};
    }

    mapFeatureDelete.init(_.extend({}, options, {
        getUrls: getUrls,
        resetUIState: function() {
            if (getTreeId() === '') {
                $('#delete-plot-warning').show();
                $('#delete-tree-warning').hide();
            } else {
                $('#delete-tree-warning').show();
                $('#delete-plot-warning').hide();
            }
        }
    }));

    function initializeTreeIdSection (id) {
        var $section = $(options.treeIdColumn);
        $section.attr('data-tree-id', id);
        $section.html(format('<a href="trees/%s/">%s</a>', id, id));
        $(options.treePresenceSection).hide();
    }

    otmTypeahead.bulkCreate(options.typeaheads);

    $('[data-date-format]').datepicker();

    diameterCalculator({ formSelector: '#map-feature-form',
                         cancelStream: form.cancelStream,
                         saveOkStream: form.saveOkStream });

    mapFeatureUdf.init(form);

    newTreeIdStream.onValue(initializeTreeIdSection);
    newTitleStream.onValue($('#map-feature-title'), 'html');
    newAddressStream.onValue($('#map-feature-address'), 'html');


    var beginAddStream = plotAddTree.init(options);
    beginAddStream.onValue($treeSection, 'show');

    form.cancelStream
        .skipUntil(beginAddStream)
        .takeUntil(newTreeIdStream)
        .onValue($treeSection, 'hide');
};
