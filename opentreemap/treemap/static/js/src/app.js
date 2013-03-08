/* app.js */

//= require OpenLayers

/*globals $,OpenLayers,otm*/
/*jslint indent: 4, white: true */

var app = (function ($,L,config) {
    "use strict";
    return {
        createBasemap: function (elmt) {
            var map = new L.Map({
                div: elmt,
                projection: 'EPSG:3857',
                layers: [
                    new L.Layer.Google(
                        "Google Streets",
                        {numZoomLevels: 20}
                    )
                ]
            });

            map.setCenter(config.instance.center, 10);

            return map;
        },

        init: function () {
            app.createBasemap($("#map")[0]);
        }
    };
}($, OpenLayers, otm.settings));


$(app.init);
