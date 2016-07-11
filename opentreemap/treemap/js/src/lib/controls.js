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
        var self = this,
            $el = $(canopyFilterTmpl()),
            changeBus = new Bacon.Bus();

        this.$el = $el;
        this.tilerArgsProp = changeBus.toProperty({
            canopyMin: 0,
            canopyMax: 1
        });

        this.$el.find('[name="canopy-slider"]').ionRangeSlider({
            type: 'double',
            min: 0,
            max: 100,
            from: 0,
            to: 100,
            step: 1,
            drag_interval: true,
            hide_min_max: true,
            hide_from_to: true,
            grid: false,
            postfix: '%',
            onChange: function (data) {
                changeBus.push({
                    canopyMin: data.from / 100,
                    canopyMax: data.to / 100
                });
            },
        });

        this.tilerArgsProp.onValue(function(value) {
            $el.find('.from-label').text(Math.floor(value.canopyMin * 100) + '%');
            $el.find('.to-label').text(Math.floor(value.canopyMax * 100) + '%');
        });
    },

    onAdd: function(map) {
        var el = this.$el.get(0);
        L.DomEvent.disableClickPropagation(el);
        return el;
    }
});

module.exports = {
    CanopyFilterControl: CanopyFilterControl
};
