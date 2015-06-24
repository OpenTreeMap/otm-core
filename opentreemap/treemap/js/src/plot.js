"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    R = require('ramda'),
    format = require('util').format,
    otmTypeahead = require('treemap/otmTypeahead'),
    FH = require('treemap/fieldHelpers'),
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
                                          '.responseData.feature.address_full');

    function initializeTreeIdSection (id) {
        var $section = $(options.treeIdColumn);
        $section.attr('data-tree-id', id);
        $section.html(format('<a href="trees/%s/">%s</a>', id, id));
        $(options.treePresenceSection).hide();
    }

    otmTypeahead.bulkCreate(options.typeaheads);

    $('[data-date-format]').datepicker();

    diameterCalculator({ formSelector: '#plot-form',
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
