"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    U = require('treemap/lib/utility.js'),
    R = require('ramda'),
    format = require('util').format,
    otmTypeahead = require('treemap/lib/otmTypeahead.js'),
    FH = require('treemap/lib/fieldHelpers.js'),
    mapFeature = require('treemap/lib/mapFeature.js'),
    mapFeatureDelete = require('treemap/lib/mapFeatureDelete.js'),
    diameterCalculator = require('treemap/lib/diameterCalculator.js'),
    mapFeatureUdf = require('treemap/lib/mapFeatureUdf.js'),
    plotAddTree = require('treemap/lib/plotAddTree.js'),
    moment = require('moment'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

// Placed onto the jquery object
require('bootstrap-datepicker');

var dom = {
    form: '#map-feature-form',
    treeIdColumn: '#tree-id-column',
    ecoBenefits: '#ecobenefits',
    treePresenceSection: '#tree-presence-section',
    beginAddTree: '#begin-add-tree',
    addTreeControls: '#add-tree-controls',
    treeSection: '#tree-details',
};

function excludeNullMap (obs, fn) {
    return obs.map(fn)
        .filter(R.not(_.isUndefined))
        .filter(R.not(_.isNull));
}

var form = mapFeature.init().inlineEditForm,
    $treeSection = $(dom.treeSection),
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
    return $(dom.treeIdColumn).attr('data-tree-id');
}

function getUrls() {
    var deleteUrl = document.URL,
        afterDeleteUrl = reverse.map(config.instance.url_name),
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

mapFeatureDelete.init({
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
});

function initializeTreeIdSection (id) {
    var $section = $(dom.treeIdColumn);
    $section.attr('data-tree-id', id);
    $section.html(format('<a href="trees/%s/">%s</a>', id, id));
    $(dom.treePresenceSection).hide();
}

otmTypeahead.create({
    name: "species",
    url: reverse.species_list_view(config.instance.url_name),
    input: "#plot-species-typeahead",
    template: "#species-element-template",
    hidden: "#plot-species-hidden",
    reverse: "id",
    forceMatch: true
});

$('[data-date-format]').datepicker();

diameterCalculator({
    formSelector: dom.form,
    cancelStream: form.cancelStream,
    saveOkStream: form.saveOkStream
});

mapFeatureUdf.init(form);

newTreeIdStream.onValue(initializeTreeIdSection);
newTitleStream.onValue($('#map-feature-title'), 'html');
newAddressStream.onValue($('#map-feature-address'), 'html');


var beginAddStream = plotAddTree.init({
    form: form,
    addTreeControls: dom.addTreeControls,
    beginAddTree: dom.beginAddTree,
    plotId: window.otm.mapFeature.plotId
});
beginAddStream.onValue($treeSection, 'show');

form.cancelStream
    .skipUntil(beginAddStream)
    .takeUntil(newTreeIdStream)
    .onValue($treeSection, 'hide');
