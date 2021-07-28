import React from 'react';
import { withLeaflet } from 'react-leaflet';
import { useLeafletContext, LayerProps,
  createTileLayerComponent,
  updateGridLayer,
  withPane } from '@react-leaflet/core';
import L from 'leaflet';
import '../L.UTFGrid-min';


export const UtfGrid = createTileLayerComponent(
    function createTileLayer({ url, ...options }, context) {
        const layer = new L.UTFGrid(url, options);

        layer.setUrl = function(url) {
            layer._url = url;
            layer._cache = {};
            layer._update();
        }

        layer.on('click', function(event) {
            if (event.id == null) return;
            //L.popup().setLatLng([event.latlng.lat, event.latlng.lng]).openOn(context.map);
        });

		//this.leafletElement = new L.UtfGrid(this.props.url, this.props.options);
        return {
            instance: layer,
            context,
        }
    },
    (layer, props, prevProps) => {
        const { url } = props;
        updateGridLayer(layer, props, prevProps);
        if (url != null && url !== prevProps.url) {
            layer.setUrl(url);
            layer.redraw();
        }
    });
    //updateGridLayer);

/*
export const UtfGrid = (props) => {
  const context = useLeafletContext();

  React.useEffect(() => {
    const container = context.layerContainer || context.map;
    const layer = new L.utfGrid(props.url, props.options);

    layer.setUrl = function(url) {
        layer._url = url;
        layer._cache = {};
        layer._update();
    }

    container.addLayer(layer);

    return () => {
      container.removeLayer(layer);
    };
  });

  return null;
};
*/

export default UtfGrid;
