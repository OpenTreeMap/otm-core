"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    R = require('ramda'),
    L = require('leaflet'),
    Bacon = require('baconjs'),
    format = require('util').format,
    U = require('treemap/lib/utility.js'),
    BU = require('treemap/lib/baconUtils.js'),
    urlState = require('treemap/lib/urlState.js'),

    layersLib = require('treemap/lib/layers.js'),
    CanopyFilterControl = require('treemap/lib/controls.js').CanopyFilterControl,

    config = require('treemap/lib/config.js'),
    reverse = require('reverse'),

    MIN_ZOOM_OPTION = layersLib.MIN_ZOOM_OPTION,
    MAX_ZOOM_OPTION = layersLib.MAX_ZOOM_OPTION,
    BASE_PANE_OPTION = layersLib.BASE_PANE_OPTION;

// Leaflet extensions
require('utfgrid');
require('leafletbing');
require('leaflet.gridlayer.googlemutant');
require('esri-leaflet');

var MapManager = function() {};  // constructor

MapManager.prototype = {
    ZOOM_DEFAULT: 11,
    ZOOM_PLOT: 18,

    createTreeMap: function (options) {
        var hasPolygons = getDomMapBool('has-polygons', options.domId),
            hasBoundaries = getDomMapBool('has-boundaries', options.domId),
            plotLayer = layersLib.createPlotTileLayer(),
            allPlotsLayer = layersLib.createPlotTileLayer(),
            utfLayer = layersLib.createPlotUTFLayer();
        this._plotLayer = plotLayer;
        this._allPlotsLayer = allPlotsLayer;
        this._utfLayer = utfLayer;
        allPlotsLayer.setOpacity(0.3);

        options.bounds = getDomMapAttribute('bounds', options.domId);
        var map = this.createMap(options);

        if (options.plotLayerViewOnly) {
            this.layersControl.addOverlay(plotLayer, 'OpenTreeMap Trees');
        } else {
            map.addLayer(plotLayer);
            map.addLayer(utfLayer);
            var baseUtfEventStream = BU.leafletEventStream(utfLayer, 'click');

            if (hasPolygons) {
                var polygonLayer = layersLib.createPolygonTileLayer(),
                    allPolygonsLayer = layersLib.createPolygonTileLayer();
                this._hasPolygons = hasPolygons;
                this._polygonLayer = polygonLayer;
                this._allPolygonsLayer = allPolygonsLayer;
                allPolygonsLayer.setOpacity(0.3);
                map.addLayer(polygonLayer);

                // When a map has polygons, we check to see if a utf event was
                // for a dot, and if not, and if the map is zoomed in enough to
                // see polygons, we make an AJAX call to see if there
                // is a polygon in that location.
                var shouldCheckForPolygon = function(e) {
                        return map.getZoom() >= MIN_ZOOM_OPTION.minZoom && e.data === null;
                    },
                    plotUtfEventStream = baseUtfEventStream.filter(R.not(shouldCheckForPolygon)),
                    emptyUtfEventStream = baseUtfEventStream.filter(shouldCheckForPolygon),

                    polygonDataStream = emptyUtfEventStream.map(function(e) {
                        var lat = e.latlng.lat,
                            lng = e.latlng.lng,
                            // The distance parameter changes as a function of zoom
                            // halving with every zoom level.  I arrived at 20
                            // meters at zoom level 15 through trial and error
                            dist = 20 / Math.pow(2, map.getZoom() - MIN_ZOOM_OPTION.minZoom),
                            url = reverse.polygon_for_point({instance_url_name: config.instance.url_name});

                        return url + format('?lng=%d&lat=%d&distance=%d', lng, lat, dist);
                    }).flatMap(BU.getJsonFromUrl);

                map.utfEvents = Bacon.mergeAll(
                    plotUtfEventStream,
                    emptyUtfEventStream.zip(polygonDataStream, function(utf, polygon) {
                        return _.merge({}, utf, polygon);
                    })
                );
            } else {
                map.utfEvents = baseUtfEventStream;
            }
        }

        if (hasBoundaries) {
            var boundariesLayer = layersLib.createBoundariesTileLayer();
            map.addLayer(boundariesLayer);
            this.layersControl.addOverlay(boundariesLayer, 'Boundaries');
        }

        if (config.instance.canopyEnabled) {
            var canopyLayer = layersLib.createCanopyBoundariesTileLayer();

            var filterControl = new CanopyFilterControl();
            filterControl.tilerArgsProp
                .debounce(1000)
                .map(function(tilerArgs) {
                    tilerArgs.category = config.instance.canopyBoundaryCategory;
                    return tilerArgs;
                })
                .onValue(function(tilerArgs) {
                    var newUrl = layersLib.getCanopyBoundariesTileLayerUrl(tilerArgs);
                    canopyLayer.setUrl(newUrl);
                });

            map.on('overlayadd', function(e) {
                if (e.layer === canopyLayer) {
                    map.addControl(filterControl);
                }
            });

            map.on('overlayremove', function(e) {
                if (e.layer === canopyLayer) {
                    map.removeControl(filterControl);
                }
            });

            this.layersControl.addOverlay(canopyLayer, 'Regional Canopy Percentages');
        }

        _.each(config.instance.customLayers, _.partial(addCustomLayer, this));

        var zoomLatLngOutputStream = trackZoomLatLng(options, map);

        return zoomLatLngOutputStream;
    },

    createMap: function (options) {
        var center = options.centerWM || {x: 0, y: 0},
            zoom = options.zoom || 2,
            bounds = options.bounds,
            map = L.map(options.domId),
            type = options.type,
            basemapMapping = getBasemapLayers(type);

        layersLib.initPanes(map);

        if (_.isUndefined(bounds)) {
            map.setView(U.webMercatorToLeafletLatLng(center.x, center.y), zoom);
        } else {
            map.fitBounds([
                    U.webMercatorToLeafletLatLng(bounds.xmin, bounds.ymin),
                    U.webMercatorToLeafletLatLng(bounds.xmax, bounds.ymax)
                ],
                MAX_ZOOM_OPTION
            );
        }

        if (_.isArray(basemapMapping)) {
            _.each(_.values(basemapMapping),
                function (layer) {
                    map.addLayer(layer);
                });
        } else {
            var visible = _.keys(basemapMapping)[0];
            map.addLayer(basemapMapping[visible]);
            this.layersControl = L.control.layers(basemapMapping, null, {
                autoZIndex: false
            }).addTo(map);
        }

        if (options.disableScrollWithMouseWheel) {
            map.scrollWheelZoom = false;
        }

        // Disables pinch-to-zoom and double-tap-to-zoom
        // This is supposed to be disabled already by user-scalable=no,
        // but iOS Safari 10+ ignores that property
        $('body').off('touchstart');
        $('body').on('touchstart', function(e) {
            if (e.originalEvent.touches.length > 1) {
                e.preventDefault(); // pinch - prevent zoom
                e.stopPropagation();
                return;
            }

            var t2 = e.timeStamp;
            var t1 = this.lastTouch || t2;
            var dt = t2 - t1;
            this.lastTouch = t2;

            if (dt && dt < 500) {
                e.preventDefault(); // double tap - prevent zoom
                e.stopPropagation();
            }
        });

        this.map = map;
        return map;
    },

    updateRevHashes: function (response) {
        this._utfLayer.setHashes(response);
        this._plotLayer.setHashes(response);
        this._allPlotsLayer.setHashes(response);

        if (this._hasPolygons) {
            this._polygonLayer.setHashes(response);
            this._allPolygonsLayer.setHashes(response);
        }
    },

    setFilter: function (filter) {
        this._plotLayer.setFilter(filter);

        if (this._hasPolygons) {
            this._polygonLayer.setFilter(filter);
        }

        if (!this._allPlotsLayer.map) {
            this.map.addLayer(this._allPlotsLayer);
            if (this._hasPolygons) {
                this.map.addLayer(this._allPolygonsLayer);
            }
        }
        if (_.isEmpty(filter)) {
            this.map.removeLayer(this._allPlotsLayer);
            if (this._hasPolygons) {
                this.map.removeLayer(this._allPolygonsLayer);
            }
        }
    },

    setCenterAndZoomLL: function (zoom, location, reset) {
        // Don't zoom out. For example, if user is choosing a tree location
        // via geolocation but is zoomed in further than ZOOM_PLOT, we don't
        // want to zoom them out.
        // Also, don't try to zoom in farther than allowed.
        var zoomToApply = Math.max(
            this.map.getZoom(),
            Math.min(zoom, this.map.getMaxZoom()));

        this.map.setView(location, zoomToApply, {reset: !!reset});
    },

    setCenterAndZoomWM: function (zoom, location, reset) {
        this.setCenterAndZoomLL(
            zoom,
            U.webMercatorToLeafletLatLng(location.x, location.y),
            reset);
    },

    setCenterWM: function(location, reset) {
        this.setCenterAndZoomWM(this.ZOOM_PLOT, location, reset);
    },

    setCenterLL: function(location, reset) {
        this.setCenterAndZoomLL(this.ZOOM_PLOT, location, reset);
    },

    customizeVertexIcons: function() {
        // Leaflet Draw has different polygon vertex icons for touch screens
        // and non-touch screens, and decides which to use based on Leaflet's
        // L.Browser.Touch. But with current browsers and Leaflet 1.0.3,
        // L.Browser.Touch is true for a browser that supports touch even when
        // you're using a non-touch device. That's why we get giant vertex
        // icons on desktop devices.
        //
        // Since for us polygon editing is unlikely to be done via touch, always
        // use the non-touch icons.
        //
        // Also change the default 8x8 square into a 10x10 circle (with help
        // from CSS on .leaflet-editing-icon)

        customize(L.Draw.Polyline.prototype);
        customize(L.Edit.PolyVerticesEdit.prototype);

        function customize(prototype) {
            var options = prototype.options;
            options.icon.options.iconSize = new L.Point(10, 10);
            options.touchIcon = options.icon;
        }
    }
};

function getBasemapLayers(type) {
    var options = _.extend({}, MAX_ZOOM_OPTION, BASE_PANE_OPTION);

    type = type || config.instance.basemap.type;

    function makeGoogleLayer(layer) {
        return L.gridLayer.googleMutant(
            _.extend(options, {type: layer}));
    }

    function makeBingLayer(layer) {
        return new L.BingLayer(
            config.bing_api_key,
            _.extend(options, {type: layer}));
    }

    function makeEsriLayer(key) {
        return L.esri.basemapLayer(key, options);
    }

    if (type === 'bing') {
        return {
            'Road': makeBingLayer('Road'),
            'Aerial': makeBingLayer('Aerial'),
            'Hybrid': makeBingLayer('AerialWithLabels')
        };
    } else if (type === 'esri') {
        return {
            'Streets': makeEsriLayer("Topographic"),
            'Hybrid': L.layerGroup([
                makeEsriLayer("Imagery"),
                makeEsriLayer("ImageryTransportation")
            ]),
            'Satellite': makeEsriLayer("Imagery")
        };
    } else if (type === 'tms') {
        return [L.tileLayer(config.instance.basemap.data, options)];
    } else {
        return {
            'Streets': makeGoogleLayer('roadmap'),
            'Hybrid': makeGoogleLayer('hybrid'),
            'Satellite': makeGoogleLayer('satellite'),
            'Terrain': makeGoogleLayer('terrain')
        };
    }
}

function trackZoomLatLng(options, map) {
    var zoomLatLngOutputStream =
        BU.leafletEventStream(map, 'moveend')
            .map(function () {
                var zoomLatLng = _.extend({zoom: map.getZoom()}, map.getCenter());
                return zoomLatLng;
            });

    if (options.trackZoomLatLng) {
        var zoomLatLngInputStream;
        if (options.zoomLatLngInputStream) {
            // Calling page will save/load zoomLatLng
            zoomLatLngInputStream = options.zoomLatLngInputStream;
        } else {
            // Save/load zoomLatLng in urlState
            zoomLatLngInputStream = urlState.stateChangeStream
                .filter('.zoomLatLng')
                .map('.zoomLatLng');
            zoomLatLngOutputStream.onValue(urlState.setZoomLatLng);
        }

        zoomLatLngInputStream.onValue(function (zoomLatLng) {
            if (!_.isEmpty(zoomLatLng)) {
                map.setView(
                    new L.LatLng(zoomLatLng.lat, zoomLatLng.lng),
                    zoomLatLng.zoom);
            }
        });
    }
    return zoomLatLngOutputStream;
}

function getDomMapBool(dataAttName, domId) {
    return (getDomMapAttribute(dataAttName, domId) == 'True');
}

function getDomMapAttribute(dataAttName, domId) {
    domId = domId || 'map';
    var $map = $('#' + domId),
        value = $map.data(dataAttName);
    return value;
}

function addCustomLayer(mapManager, layerInfo) {
    var layer = layersLib.createCustomLayer(layerInfo);
    mapManager.layersControl.addOverlay(layer, layerInfo.name);
    if (layerInfo.showByDefault) {
        mapManager.map.addLayer(layer);
    }
}

module.exports = MapManager;
