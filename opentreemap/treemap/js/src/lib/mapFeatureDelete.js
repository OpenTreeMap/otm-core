"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    U = require('treemap/lib/utility.js'),
    MapManager = require('treemap/lib/MapManager.js'),
    toastr = require('toastr'),
    reverse = require('reverse'),
    config = require('treemap/lib/config.js');

var dom = {
    delete: '#delete-object',
    deleteConfirm: '#delete-confirm',
    deleteCancel: '#delete-cancel',
    deleteConfirmationBox: '#delete-confirmation-box',
    spinner: '.spinner'
};

exports.init = function(options) {
    options = options || {};

    $(dom.deleteConfirm).on('click', function () {
        var deleteUrl = options.deleteUrl || document.URL,
            successUrl = options.successUrl || mapPageUrl();
        $(dom.spinner).show();
        $.ajax({
            url: deleteUrl,
            type: 'DELETE',
            success: function () {
                window.location = successUrl;
            },
            error: function () {
                toastr.error("Cannot delete");
            }
        });
    });

    $(dom.deleteCancel).on('click', function () {
        $(dom.deleteConfirmationBox).hide();
    });
    $(dom.delete).on('click', function () {
        $(dom.deleteConfirmationBox).show();
    });
};

function mapPageUrl() {
    // Make a URL for the map page, zoomed to the current feature location
    var location = window.otm.mapFeature.location.point,
        latlng = U.webMercatorToLatLng(location.x, location.y),
        zoom = (new MapManager()).ZOOM_PLOT,
        zoomLatLng = _.extend({zoom: zoom}, latlng),
        query = U.makeZoomLatLngQuery(zoomLatLng),
        url = reverse.map(config.instance.url_name) + '?z=' + query;
    return url;
}