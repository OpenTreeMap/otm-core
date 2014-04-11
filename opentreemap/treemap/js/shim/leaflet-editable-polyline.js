L.Polyline.polylineEditor = L.Polygon.extend({
    _prepareMapIfNeeded: function() {
        var that = this;

        if(this._map._editablePolylines != null) {
            return
        }

        // Container for all editable polylines on this map:
        this._map._editablePolylines = [];
        this._map._editablePolylinesEnabled = true;

        // Click anywhere on map to add a new point-polyline:
        if(this._options.newPolylines) {
            console.log('click na map');
            that._map.on('dblclick', function(event) {
                console.log('click, target=' + (event.target == that._map) + ' type=' + event.type);
                if(that._map.isEditablePolylinesBusy())
                    return;

                var latLng = event.latlng;
                if(that._options.newPolylineConfirmMessage)
                    if(!confirm(that._options.newPolylineConfirmMessage))
                        return

                var contexts = [{'originalPolylineNo': null, 'originalPointNo': null}];
                L.Polyline.PolylineEditor([latLng], that._options, contexts).addTo(that._map);

                that._showBoundMarkers();
            });
        }

        /**
         * Check if there is *any* busy editable polyline on this map.
         */
        this._map.isEditablePolylinesBusy = function() {
            var map = this;
            for(var i = 0; i < map._editablePolylines.length; i++)
                if(map._editablePolylines[i]._isBusy())
                    return true;

            return false;
        };

        /**
         * Enable/disable editing.
         */
        this._map.setEditablePolylinesEnabled = function(enabled) {
            var map = this;
            map._editablePolylinesEnabled = enabled;
            for(var i = 0; i < map._editablePolylines.length; i++) {
                var polyline = map._editablePolylines[i];
                if(enabled) {
                    polyline._showBoundMarkers();
                } else {
                    polyline._hideAll();
                }
            }
        };

        /*
         * Utility method added to this map to retreive editable 
         * polylines.
         */
        this._map.getEditablePolylines = function() {
            var map = this;
            return map._editablePolylines;
        }

        this._map.fixAroundEditablePoint = function(marker) {
            var map = this;
            for(var i = 0; i < map._editablePolylines.length; i++) {
                var polyline = map._editablePolylines[i];
                polyline._reloadPolyline(marker);
            }
        }
    },
    /**
     * Will add all needed methods to this polyline.
     */
    _addMethods: function() {
        var that = this;

        this._init = function(options, contexts) {
            this._prepareMapIfNeeded();

            /**
             * Since all point editing is done by marker events, markers 
             * will be the main holder of the polyline points locations.
             * Every marker contains a reference to the newPointMarker 
             * *before* him (=> the first marker has newPointMarker=null).
             */
            this._parseOptions(options);

            this._markers = [];
            var points = this.getLatLngs();
            var length = points.length;
            for(var i = 0; i < length; i++) {
                var marker = this._addMarkers(i, points[i]);
                if(! ('context' in marker)) {
                    marker.context = {}
                    if(that._contexts != null) {
                        marker.context = contexts[i];
                    }
                }

                if(marker.context && ! ('originalPointNo' in marker.context))
                    marker.context.originalPointNo = i;
                if(marker.context && ! ('originalPolylineNo' in marker.context))
                    marker.context.originalPolylineNo = that._map._editablePolylines.length;
            }

            // Map move => show different editable markers:
            var map = this._map;
            this._map.on("zoomend", function(e) {
                that._showBoundMarkers();
            });
            this._map.on("moveend", function(e) {
                that._showBoundMarkers();
            });

            if(this._desiredPolylineNo && this._desiredPolylineNo != null) {
                this._map._editablePolylines.splice(this._desiredPolylineNo, 0, this);
            } else {
                this._map._editablePolylines.push(this);
            }
        };

        /**
         * Check if is busy adding/moving new nodes. Note, there may be 
         * *other* editable polylines on the same map which *are* busy.
         */
        this._isBusy = function() {
            return that._busy;
        };

        this._setBusy = function(busy) {
            that._busy = busy;
        };

        /**
         * Get markers for this polyline.
         */
        this.getPoints = function() {
            return this._markers;
        };

        this._parseOptions = function(options) {
            if(!options)
                options = {};

            // Do not show edit markers if more than maxMarkers would be shown:
            if(!('maxMarkers' in options))
                options.maxMarkers = 100;
            if(!('newPolylines' in options))
                options.newPolylines = false;
            if(!('newPolylineConfirmMessage' in options))
                options.newPolylineConfirmMessage = '';
            if(!('addFirstLastPointEvent' in options))
                options.addFirstLastPointEvent = 'click';
            if(!('customPointListeners' in options))
                options.customPointListeners = {};
            if(!('customNewPointListeners' in options))
                options.customNewPointListeners = {};

            this._options = options;

            // Icons:
            if(!options.pointIcon)
                this._options.pointIcon = L.icon({ iconUrl: 'editmarker.png', iconSize: [11, 11], iconAnchor: [6, 6] });
            if(!options.newPointIcon)
                this._options.newPointIcon = L.icon({ iconUrl: 'editmarker2.png', iconSize: [11, 11], iconAnchor: [6, 6] });
        };

        /**
         * Show only markers in current map bounds *is* there are only a certain 
         * number of markers. This method is called on eventy that change map 
         * bounds.
         */
        this._showBoundMarkers = function() {
            if (!that._map) {
                return;
            }
            
            this._setBusy(false);

            if(!that._map._editablePolylinesEnabled) {
                console.log('Do not show because editing is disabled');
                return;
            }

            var bounds = that._map.getBounds();
            var found = 0;
            for(var polylineNo in that._map._editablePolylines) {
                var polyline = that._map._editablePolylines[polylineNo];
                for(var markerNo in polyline._markers) {
                    var marker = polyline._markers[markerNo];
                    if(bounds.contains(marker.getLatLng()))
                        found += 1;
                }
            }

            for(var polylineNo in that._map._editablePolylines) {
                var polyline = that._map._editablePolylines[polylineNo];
                for(var markerNo in polyline._markers) {
                    var marker = polyline._markers[markerNo];
                    if(found < that._options.maxMarkers) {
                        that._setMarkerVisible(marker, bounds.contains(marker.getLatLng()));
                        that._setMarkerVisible(marker.newPointMarker, bounds.contains(marker.getLatLng()));
                    } else {
                        that._setMarkerVisible(marker, false);
                        that._setMarkerVisible(marker.newPointMarker, false);
                    }
                }
            }
        };

        /**
         * Used when adding/moving points in order to disable the user to mess 
         * with other markers (+ easier to decide where to put the point 
         * without too many markers).
         */
        this._hideAll = function(except) {
            this._setBusy(true);
            for(var polylineNo in that._map._editablePolylines) {
                console.log("hide " + polylineNo + " markers");
                var polyline = that._map._editablePolylines[polylineNo];
                for(var markerNo in polyline._markers) {
                    var marker = polyline._markers[markerNo];
                    if(except == null || except != marker)
                        polyline._setMarkerVisible(marker, false);
                    if(except == null || except != marker.newPointMarker)
                        polyline._setMarkerVisible(marker.newPointMarker, false);
                }
            }
        }

        /**
         * Show/hide marker.
         */
        this._setMarkerVisible = function(marker, show) {
            if(!marker)
                return;

            var map = this._map;
            if(show) {
                if(!marker._visible) {
                    if(!marker._map) { // First show for this marker:
                        marker.addTo(map);
                    } else { // Marker was already shown and hidden:
                        map.addLayer(marker);
                    }
                    marker._map = map;
                }
                marker._visible = true;
            } else {
                if(marker._visible) {
                    map.removeLayer(marker);
                }
                marker._visible = false;
            }
        };

        /**
         * Reload polyline. If it is busy, then the bound markers will not be 
         * shown. 
         */
        this._reloadPolyline = function(fixAroundPointNo) {
            that.setLatLngs(that._getMarkerLatLngs());
            if(fixAroundPointNo != null)
                that._fixAround(fixAroundPointNo);
            that._showBoundMarkers();
        }

        /**
         * Add two markers (a point marker and his newPointMarker) for a 
         * single point.
         *
         * Markers are not added on the map here, the marker.addTo(map) is called 
         * only later when needed first time because of performance issues.
         */
        this._addMarkers = function(pointNo, latLng, fixNeighbourPositions) {
            var that = this;
            var points = this.getLatLngs();
            var marker = L.marker(latLng, {draggable: true, icon: this._options.pointIcon});

            marker.newPointMarker = null;
            marker.on('dragstart', function(event) {
                var pointNo = that._getPointNo(event.target);
                var previousPoint = that._getPrevMarker(pointNo).getLatLng();
                var nextPoint = that._getNextMarker(pointNo).getLatLng();
                that._setupDragLines(marker, previousPoint, nextPoint);
                that._hideAll(marker);
            });
            marker.on('dragend', function(event) {
                var marker = event.target;
                var pointNo = that._getPointNo(event.target);
                setTimeout(function() {
                    that._reloadPolyline(pointNo);
                }, 25);
            });
            marker.on('contextmenu', function(event) {
                var marker = event.target;
                var pointNo = that._getPointNo(event.target);
                that._map.removeLayer(marker);
                that._map.removeLayer(newPointMarker);
                that._markers.splice(pointNo, 1);
                that._reloadPolyline(pointNo);
            });
            marker.on(that._options.addFirstLastPointEvent, function(event) {

                console.log('click on marker');
                var marker = event.target;
                var pointNo = that._getPointNo(event.target);
                console.log('pointNo=' + pointNo + ' that._markers.length=' + that._markers.length);
                event.dont;
                if(pointNo == 0 || pointNo == that._markers.length - 1) {
                    console.log('first or last');
                    that._prepareForNewPoint(marker, pointNo == 0 ? 0 : pointNo + 1);
                } else {
                    console.log('not first or last');
                }
            });

            var previousPoint = points[pointNo == 0 ? points.length - 1 : pointNo - 1];
            var newPointMarker = L.marker([(latLng.lat + previousPoint.lat) / 2.,
                                           (latLng.lng + previousPoint.lng) / 2.],
                                          {draggable: true, icon: this._options.newPointIcon});
            marker.newPointMarker = newPointMarker;
            newPointMarker.on('dragstart', function(event) {
                var pointNo = that._getPointNo(event.target);
                var previousPoint = that._getPrevMarker(pointNo).getLatLng();
                var nextPoint = that._markers[pointNo].getLatLng();
                that._setupDragLines(marker.newPointMarker, previousPoint, nextPoint);

                that._hideAll(marker.newPointMarker);
            });
            newPointMarker.on('dragend', function(event) {
                var marker = event.target;
                var pointNo = that._getPointNo(event.target);
                that._addMarkers(pointNo, marker.getLatLng(), true);
                setTimeout(function() {
                    that._reloadPolyline();
                }, 25);
            });
            newPointMarker.on('contextmenu', function(event) {
                // 1. Remove this polyline from map
                var marker = event.target;
                var pointNo = that._getPointNo(marker);
                var markers = that.getPoints();
                that._hideAll();

                var secondPartMarkers = that._markers.slice(pointNo, pointNo.length);
                that._markers.splice(pointNo, that._markers.length - pointNo);

                that._reloadPolyline();

                var points = [];
                var contexts = [];
                for(var i = 0; i < secondPartMarkers.length; i++) {
                    var marker = secondPartMarkers[i];
                    points.push(marker.getLatLng());
                    contexts.push(marker.context);
                }

                console.log('points:' + points);
                console.log('contexts:' + contexts);

                // Need to know the current polyline order numbers, because 
                // the splitted one need to be inserted immediately after:
                var originalPolylineNo = that._map._editablePolylines.indexOf(that);

                L.Polyline.PolylineEditor(points, that._options, contexts, originalPolylineNo + 1)
                                          .addTo(that._map);

                that._showBoundMarkers();
            });

            this._markers.splice(pointNo, 0, marker);

            // User-defined custom event listeners:
            if(that._options.customPointListeners)
                for(var eventName in that._options.customPointListeners)
                    marker.on(eventName, that._options.customPointListeners[eventName]);
            if(that._options.customNewPointListeners)
                for(var eventName in that._options.customNewPointListeners)
                    newPointMarker.on(eventName, that._options.customNewPointListeners[eventName]);

            if(fixNeighbourPositions) {
                this._fixAround(pointNo);
            }

            return marker;
        };

        /**
         * Event handlers for first and last point.
         */
        this._prepareForNewPoint = function(marker, pointNo) {
            // This is slightly delayed to prevent the same propagated event 
            // to be catched here:
            setTimeout(
                function() {
                    that._hideAll();
                    that._setupDragLines(marker, marker.getLatLng());
                    that._map.once('click', function(event) {
                        console.log('dodajemo na ' + pointNo + ' - ' + event.latlng);
                        that._addMarkers(pointNo, event.latlng, true);
                        that._reloadPolyline();
                    });
                },
                100
            );
        };

        /**
         * Fix nearby new point markers when the new point is created.
         */
        this._fixAround = function(pointNoOrMarker) {
            if((typeof pointNoOrMarker) == 'number')
                var pointNo = pointNoOrMarker;
            else
                var pointNo = that._markers.indexOf(pointNoOrMarker);

            if(pointNo < 0)
                return;

            var previousMarker = that._getPrevMarker(pointNo);
            var marker = that._markers[pointNo];
            var nextMarker = that._getNextMarker(pointNo);
            if(marker && previousMarker) {
                marker.newPointMarker.setLatLng([(previousMarker.getLatLng().lat + marker.getLatLng().lat) / 2.,
                                                 (previousMarker.getLatLng().lng + marker.getLatLng().lng) / 2.]);
            }
            if(marker && nextMarker) {
                nextMarker.newPointMarker.setLatLng([(marker.getLatLng().lat + nextMarker.getLatLng().lat) / 2.,
                                                     (marker.getLatLng().lng + nextMarker.getLatLng().lng) / 2.]);
            }
        };

        /**
         * Find the order number of the marker.
         */
        this._getPointNo = function(marker) {
            for(var i = 0; i < this._markers.length; i++) {
                if(marker == this._markers[i] || marker == this._markers[i].newPointMarker) {
                    return i;
                }
            }
            return -1;
        };

        /**
         * Get previous marker, handling edge case.
         */
        this._getPrevMarker = function(markerNo) {
            var lastIndex = this._markers.length - 1,
                prevMarkerNo = markerNo == 0 ? lastIndex : markerNo - 1,
                prevMarker = this._markers[prevMarkerNo];
            return prevMarker;
        };

        /**
         * Get next marker, handling edge case.
         */
        this._getNextMarker = function(markerNo) {
            var lastIndex = this._markers.length - 1,
                nextMarkerNo = markerNo < lastIndex ? markerNo + 1 : 0,
                nextMarker = this._markers[nextMarkerNo];
            return nextMarker;
        };

        /**
         * Get polyline latLngs based on marker positions.
         */
        this._getMarkerLatLngs = function() {
            var result = [];
            for(var i = 0; i < this._markers.length; i++)
                result.push(this._markers[i].getLatLng());
            return result;
        };

        this._setupDragLines = function(marker, point1, point2) {
            var line1 = null;
            var line2 = null;
            if(point1) line1 = L.polyline([marker.getLatLng(), point1], {dasharray: "5,1", weight: 1})
                                .addTo(that._map);
            if(point2) line2 = L.polyline([marker.getLatLng(), point2], {dasharray: "5,1", weight: 1})
                                .addTo(that._map);

            var moveHandler = function(event) {
                if(line1)
                    line1.setLatLngs([event.latlng, point1]);
                if(line2)
                    line2.setLatLngs([event.latlng, point2]);
            };

            var stopHandler = function(event) {
                if (that._map) {
                    that._map.off('mousemove', moveHandler);
                    marker.off('dragend', stopHandler);
                    if(line1) that._map.removeLayer(line1);
                    if(line2) that._map.removeLayer(line2);
                    console.log('STOPPED');
                    // Causes a Leaflet exception on every drag -RM 20140326
                    // if(event.target != that._map) {
                    //     that._map.fire('click', event);
                    // }
                }
            };

            that._map.on('mousemove', moveHandler);
            marker.on('dragend', stopHandler);

            that._map.once('click', stopHandler);
            marker.once('click', stopHandler);
            if(line1) line1.once('click', stopHandler);
            if(line2) line2.once('click', stopHandler);
        }
    }
});

L.Polyline.polylineEditor.addInitHook(function () {

    this.on('add', function(event) {
        this._map = event.target._map;
        this._addMethods();

        /**
         * When addint a new point we must disable the user to mess with other 
         * markers. One way is to check everywhere if the user is busy. The 
         * other is to just remove other markers when the user is doing 
         * somethinng.
         *
         * TODO: Decide the right way to do this and then leave only _busy or 
         * _hideAll().
         */
        this._busy = false;
        this._initialized = false;

        this._init(this._options, this._contexts);

        this._initialized = true;

        return this;
    });

    this.on('remove', function(event) {
        var polyline = event.target;
        var map = polyline._map;
        var polylines = map.getEditablePolylines();
        var index = polylines.indexOf(polyline);
        if (index > -1) {
            polylines.splice(index, 1);
        }
    });
});

/**
 * Construct a new editable polyline.
 *
 * latlngs    ... a list of points (or two-element tuples with coordinates)
 * options    ... polyline options
 * contexts   ... custom contexts for every point in the polyline. Must have the 
 *                same number of elements as latlngs and this data will be 
 *                preserved when new points are added or polylines splitted.
 * polylineNo ... insert this polyline in a specific order (used when splitting).
 *
 * More about contexts:
 * This is an array of objects that will be kept as "context" for every 
 * point. Marker will keep this value as marker.context. New markers will 
 * have context set to null.
 *
 * Contexts must be the same size as the polyline size!
 *
 * By default, even without calling this method -- every marker will have 
 * context with one value: marker.context.originalPointNo with the 
 * original order number of this point. The order may change if some 
 * markers before this one are delted or new added.
 */
L.Polyline.PolylineEditor = function(latlngs, options, contexts, polylineNo) {
    // Since the app code may not be able to explicitly call the 
    // initialization of all editable polylines (if the user created a new 
    // one by splitting an existing), with this method you can control the 
    // options for new polylines:
    if(options.prepareOptions) {
        options.prepareOptions(options);
    }

    var result = new L.Polyline.polylineEditor(latlngs, options);
    result._options = options;
    result._contexts = contexts;
    result._desiredPolylineNo = polylineNo

    return result;
};
