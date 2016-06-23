"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    L = require('leaflet'),
    Bacon = require('baconjs');

require('ionRangeSlider');

var canopyFilterTmpl = _.template($('#canopy-filter-tmpl').html());

var CanopyFilterControl = L.Control.extend({
    options: {
        position: 'bottomleft'
    },

    initialize: function() {
        this._changeBus = new Bacon.Bus();
        this.tilerArgsProp = this._changeBus.toProperty({
            canopyMin: 0,
            canopyMax: 1
        });
    },

    onAdd: function(map) {
        var self = this,
            $el = $(canopyFilterTmpl());

        $el.find('[name="canopy-slider"]').ionRangeSlider({
            type: 'double',
            min: 0,
            max: 100,
            from: 0,
            to: 100,
            step: 1,
            drag_interval: true,
            hide_min_max: true,
            grid: false,
            postfix: '%',
            onChange: function (data) {
                self._changeBus.push({
                    canopyMin: data.from / 100,
                    canopyMax: data.to / 100
                });
            },
        });

        var el = $el.get(0);
        L.DomEvent.disableClickPropagation(el);
        return el;
    }
});

module.exports = CanopyFilterControl;
