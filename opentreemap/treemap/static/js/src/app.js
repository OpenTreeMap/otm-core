/* app.js */

//= require OpenLayers
//= require openlayers.layer.otm
//= require Search

/*globals $,OpenLayers,otm,document,Search*/
/*jslint indent: 4, white: true */

var app = (function ($,OL,Search,config) {
    "use strict";
    return {
        createMap: function (elmt) {
            var map = new OL.Map({
                theme: null,
                div: elmt,
                projection: 'EPSG:3857',
                layers: this.getBasemapLayers(config)
            });

            return map;
        },

        getBasemapLayers: function (config) {
            var layer;
            if (config.instance.basemap.type === 'bing') {
                layer = new OL.Layer.Bing({
                    name: 'Road',
                    key: config.instance.basemap.bing_api_key,
                    type: 'Road',
                    isBaseLayer: true
                });
            } else if (config.instance.basemap.type === 'tms') {
                layer = new OL.Layer.XYZ(
                    'xyz',
                    config.instance.basemap.data);
            } else {
                layer = new OL.Layer.Google(
                    "Google Streets",
                    {numZoomLevels: 20});
            }
            return [layer];
        },

        getPlotLayerURL: function(config, extension) {
            return '/tile/' +
                config.instance.rev +
                '/database/otm/table/treemap_plot/${z}/${x}/${y}.' +
                extension;
        },

        createPlotTileLayer: function(config) {
            return new OL.Layer.OTM(
                'tiles',
                this.getPlotLayerURL(config, 'png'),
            { isBaseLayer: false,
              filterQueryArgumentName: config.urls.filterQueryArgumentName });
        },

        getBoundsLayerURL: function(config, extension) {
            return '/tile/' +
                config.instance.rev +
                '/database/otm/table/treemap_boundary/${z}/${x}/${y}.' +
                extension;
        },

        createBoundsTileLayer: function(config) {
            return new OL.Layer.OTM(
                'bounds',
                this.getBoundsLayerURL(config, 'png'),
            { isBaseLayer: false });
        },

        createPlotUTFLayer: function(config) {
            return new OL.Layer.UTFGrid({
                url: this.getPlotLayerURL(config, 'grid.json') +
                    '?interactivity=id',
                utfgridResolution: 4
            });
        },

        /**
         * Create a new utf movement control bound to all
         * utf layers.
         *
         * @param renderfn A single argument function
         *                 that takes in a hash of the last
         *                 point or 'undefined' if the mouse
         *                 isn't over a point
         */
        createUTFMovementControl: function(renderfn) {
            return new OL.Control.UTFGrid({
                callback: function(info) {
                    var idx, props;
                    for(idx in info) {
                        if (info.hasOwnProperty(idx)) {
                            props = info[idx] || {};
                            renderfn(props.data);
                        }
                    }
                },

                handlerMode: "move"
            });
        },

        onMove: function(data) {
            document.getElementById("attrs").innerHTML = JSON.stringify(data || {});
        },

        init: function () {
            var map = app.createMap($("#map")[0]),
                plotLayer = app.createPlotTileLayer(config),
                boundsLayer = app.createBoundsTileLayer(config),
                utfLayer = app.createPlotUTFLayer(config),
                zoom = 0;

            // Bing maps uses a 1-based zoom so XYZ layers
            // on the base map have a zoom offset that is
            // always one less than the map zoom:
            // > map.setCenter(center, 11)
            // > map.zoom
            //   12
            // So this forces the tile requests to use
            // the correct Z offset
            if (config.instance.basemap.type === 'bing') {
                plotLayer.zoomOffset = 1;
                utfLayer.zoomOffset = 1;
            }

            map.addLayer(plotLayer);
            map.addLayer(utfLayer);
            map.addLayer(boundsLayer);

            map.addControl(app.createUTFMovementControl(app.onMove));

            zoom = map.getZoomForResolution(76.43702827453613);
            map.setCenter(config.instance.center, zoom);

            Search.init($("#perform-search")
                        .asEventStream("click"), plotLayer);
        }
    };
}($, OpenLayers, Search, otm.settings));
