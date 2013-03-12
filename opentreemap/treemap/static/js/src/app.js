/* app.js */

//= require OpenLayers

/*globals $,OpenLayers,otm*/
/*jslint indent: 4, white: true */

var app = (function ($,L,config) {
    "use strict";
    return {
        createMap: function (elmt) {
            var map = new L.Map({
                div: elmt,
                projection: 'EPSG:3857',
                layers: this.getBasemapLayers(config)
            });

            map.setCenter(config.instance.center, 10);

            return map;
        },

        getBasemapLayers: function (config) {
            var layer;
            if (config.instance.basemap.type === 'bing') {
                layer = new L.Layer.Bing({
                    name: 'Road',
                    key: config.instance.basemap.bing_api_key,
                    type: 'Road'
                });
            } else if (config.instance.basemap.type === 'tms') {
                layer = new L.Layer.XYZ(
                    'xyz',
                    config.instance.basemap.data);
            } else {
                layer = new L.Layer.Google(
                    "Google Streets",
                    {numZoomLevels: 20});
            }
            return [layer];
        },

        createPlotTileLayer: function(config) {
            return new L.Layer.XYZ(
                'tiles',
                '/tile/' +
                    config.instance.rev +
                    '/database/otm/table/treemap_plot/${z}/${x}/${y}.png',
            { isBaseLayer: false });

        },

        init: function () {
            var map = app.createMap($("#map")[0]);
            map.addLayer(app.createPlotTileLayer(config));
        }
    };
}($, OpenLayers, otm.settings));


$(app.init);
