import { createLayerComponent } from '@react-leaflet/core';
import {bingLayer} from './leaflet.bing';

const createLeafletElement = (props) => {

    const instance = L.bingLayer(props.bingkey, props);

    return { instance };
  }

export const BingLayer = createLayerComponent(createLeafletElement);
