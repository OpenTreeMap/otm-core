"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    R = require('ramda'),
    otmTypeahead = require('treemap/lib/otmTypeahead.js'),
    mapFeatureDelete = require('treemap/lib/mapFeatureDelete.js'),
    diameterCalculator = require('treemap/lib/diameterCalculator.js'),
    mapFeatureUdf = require('treemap/lib/mapFeatureUdf.js'),
    plotAddTree = require('treemap/lib/plotAddTree.js'),
    moment = require('moment'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

var dom = {
    form: '#map-feature-form',
    treePresenceSection: '#tree-presence-section',
    beginAddTree: '#begin-add-tree',
    addTreeControls: '#add-tree-controls',
    treeSection: '#tree-details',
};

exports.init = function(form) {
    function excludeNullMap(obs, fn) {
        return obs.map(fn)
            .filter(R.complement(_.isUndefined))
            .filter(R.complement(_.isNull));
    }

    var treeId = $(dom.treeSection).attr('data-tree-id'),
        newTreeIdStream = excludeNullMap(form.saveOkStream,
            '.responseData.treeId');

    if (treeId) {
        var deleteUrl = reverse.delete_tree({
                instance_url_name: config.instance.url_name,
                feature_id: window.otm.mapFeature.featureId,
                tree_id: treeId
            });
        mapFeatureDelete.init({
            deleteUrl: deleteUrl,
            successUrl: document.URL
        });
    } else {
        mapFeatureDelete.init();
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
    
    diameterCalculator({
        formSelector: dom.form,
        cancelStream: form.cancelStream,
        saveOkStream: form.saveOkStream
    });
    
    mapFeatureUdf.init(form);

    var beginAddStream = plotAddTree.init({
        form: form,
        addTreeControls: dom.addTreeControls,
        beginAddTree: dom.beginAddTree,
        plotId: window.otm.mapFeature.featureId
    });
    beginAddStream.onValue(function () {
        $(dom.treeSection).show();
    });
    
    form.cancelStream
        .skipUntil(beginAddStream)
        .takeUntil(newTreeIdStream)
        .onValue(function () {
            $(dom.treeSection).hide();
        });
};
