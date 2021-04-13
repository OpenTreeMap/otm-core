import { useEffect } from 'react';
import {
	MapLayer, withLeaflet
} from 'react-leaflet';
import * as PropTypes from 'prop-types';
import vectorTileLayer from 'leaflet-vector-tile-layer';
import DebugFactory from 'debug';

import 'leaflet.vectorgrid';

import { useLeafletContext, LayerProps,
  createTileLayerComponent,
  updateGridLayer,
  withPane } from '@react-leaflet/core';

const debug = DebugFactory('VectorTileLayer');

import L from 'leaflet';


export const VectorTileLayer = createTileLayerComponent(
    function createTileLayer({ url, ...props }, context) {
        const container = context.layerContainer || context.map;
		const {
			activeStyle,
			hoverStyle,
			onClick,
			onDblclick,
			onMouseout,
			onMouseover,
			style,
			...options
		} = props; // extract the url, rest are the options to maintain compatibility with vector tile layer.
		debug('createLeafletElement', {
			url,
			options
		});
        useEffect(() => {
            const {
                layerContainer
            } = context.layerContainer || context.map;
            const {
                tooltipClassName = '', tooltip = null, popup = null
            } = props;
            //this.leafletElement.addTo(layerContainer);
            // bind tooltip
            if (tooltip) {
                /*this.leafletElement.bindTooltip((layer) => {
                    if (isFunction(tooltip)) {
                        return tooltip(layer);
                    } else if (isString(tooltip) && layer.properties.hasOwnProperty(tooltip)) {
                        return layer.properties[tooltip];
                    } else if (isString(tooltip)) {
                        return tooltip;
                    }
                    return '';
                }, {
                    sticky: true,
                    direction: 'auto',
                    className: tooltipClassName
                });
                */
            }
            // bind popup
            if (popup) {
                /*
                this.leafletElement.bindPopup((layer) => {
                    if (isFunction(popup)) {
                        return popup(layer);
                    } else if (isString(popup)) {
                        return popup;
                    }
                    return '';
                });
                */
            }
        }, []);

		//const layer = vectorTileLayer(url, options);
        const layer = L.vectorGrid.protobuf(url, {
            interactive: true,
            rendererFactory: L.svg.tile,
            attribution: props.attribution,
            vectorTileLayerStyles: {
                points: {
                    weight: 0.5,
                    opacity: 1,
                    color: '#ccc',
                    fillColor: '#390870',
                    fillOpacity: 0.6,
                    fill: true,
                    stroke: true
                },
                debug: {
                    stroke: false
                },
                groups: {
                    stroke: false
                },
                lines: {
                    stroke: false
                }
		 	}
        }).on('mouseover', (e) => {
				const {
					properties
				} = e.layer;
				//this._propagateEvent(onMouseover, e);

				// on mouseover styling
				let st;
				const featureId = this._getFeatureId(e.layer);
				if (isFunction(hoverStyle)) {
					st = hoverStyle(properties);
				} else if (isObject(hoverStyle)) {
					st = Object.assign({}, hoverStyle);
				}
				if (!isEmpty(st) && featureId) {
					//this.clearHighlight();
					//this.highlight = featureId;
					const base = Object.assign({}, baseStyle(properties));
					const hover = Object.assign(base, st);
					//this.setFeatureStyle(featureId, hover);
				}
			})
			.on('mouseout', (e) => {
                console.log('mouseout');
				//this._propagateEvent(onMouseout, e);
				//this.clearHighlight();
			})
			.on('click', (e) => {
				const {
					properties
				} = e.layer;
                debugger;
				const featureId = this._getFeatureId(e.layer);

				this._propagateEvent(onClick, e);

				// set active style
				let st;
				if (isFunction(activeStyle)) {
					st = activeStyle(properties);
				} else if (isObject(activeStyle)) {
					st = Object.assign({}, activeStyle);
				}
				if (!isEmpty(st) && featureId) {
					//this.clearActive();
					//this.active = featureId;
					const base = Object.assign({}, baseStyle(properties));
					const active = Object.assign(base, st);
					//this.setFeatureStyle(featureId, active);
				}
			})
			.on('dblclick', (e) => {
                console.log('double click');
				//this._propagateEvent(onDblclick, e);
				//this.clearActive();
			});

        return {
            instance: layer,
            context,
        }
    },
    updateGridLayer);


/*
class VectorTileLayer extends MapLayer {
	static propTypes = {
		leaflet: PropTypes.shape({
			map: PropTypes.object.isRequired,
			pane: PropTypes.object,
			layerContainer: PropTypes.object.isRequired
		}),
		url: PropTypes.string.isRequired
	};

	createLeafletElement(props) {
		const {
			map,
			pane,
			layerContainer
		} = props.leaflet;
		const {
			activeStyle,
			hoverStyle,
			onClick,
			onDblclick,
			onMouseout,
			onMouseover,
			style,
			url,
			...options
		} = props; // extract the url, rest are the options to maintain compatibility with vector tile layer.
		debug('createLeafletElement', {
			url,
			options
		});
		// 	zIndex,
		// 	style,
		// 	hoverStyle,
		// 	activeStyle,
		// 	onClick,
		// 	onMouseover,
		// 	onMouseout,
		// 	onDblclick,
		// 	interactive = true,
		// 	vectorTileLayerStyles,
		// 	url,
		// 	maxNativeZoom,
		// 	maxZoom,
		// 	minZoom,
		// 	subdomains,
		// 	key,
		// 	token
		// } = props;

		// get feature base styling
		// const baseStyle = (properties, zoom) => {
		// 	if (_.isFunction(style)) {
		// 		return style(properties);
		// 	} else if (_.isObject(style)) {
		// 		return style;
		// 	}
		// 	return {
		// 		weight: 0.5,
		// 		opacity: 1,
		// 		color: '#ccc',
		// 		fillColor: '#390870',
		// 		fillOpacity: 0.6,
		// 		fill: true,
		// 		stroke: true
		// 	};
		// };
		// this.highlight = null;
		// this.active = null;


		// const url = 'https://{s}.example.com/tiles/{z}/{x}/{y}.pbf';
		// const options = {
		//         // Specify zoom range in which tiles are loaded. Tiles will be
		//         // rendered from the same data for Zoom levels outside the range.
		//         minDetailZoom, // default undefined
		//         maxDetailZoom, // default undefined

		//         // Styling options for L.Polyline or L.Polygon. If it is a function, it
		//         // will be passed the vector-tile feature and the layer name as
		//         // parameters.
		//         style, // default undefined

		//         // This works like the same option for `Leaflet.VectorGrid`.
		//         vectorTileLayerStyle, // default undefined
		// };

		const layer = vectorTileLayer(url, options);

		// need to extract the mouse events from props.
		// need to check if the mouse events are defined.
		return layer
			.on('mouseover', (e) => {
				const {
					properties
				} = e.layer;
				this._propagateEvent(onMouseover, e);

				// on mouseover styling
				let st;
				const featureId = this._getFeatureId(e.layer);
				if (isFunction(hoverStyle)) {
					st = hoverStyle(properties);
				} else if (isObject(hoverStyle)) {
					st = Object.assign({}, hoverStyle);
				}
				if (!isEmpty(st) && featureId) {
					this.clearHighlight();
					this.highlight = featureId;
					const base = Object.assign({}, baseStyle(properties));
					const hover = Object.assign(base, st);
					this.setFeatureStyle(featureId, hover);
				}
			})
			.on('mouseout', (e) => {
				this._propagateEvent(onMouseout, e);
				this.clearHighlight();
			})
			.on('click', (e) => {
				const {
					properties
				} = e.layer;
				const featureId = this._getFeatureId(e.layer);

				this._propagateEvent(onClick, e);

				// set active style
				let st;
				if (isFunction(activeStyle)) {
					st = activeStyle(properties);
				} else if (isObject(activeStyle)) {
					st = Object.assign({}, activeStyle);
				}
				if (!isEmpty(st) && featureId) {
					this.clearActive();
					this.active = featureId;
					const base = Object.assign({}, baseStyle(properties));
					const active = Object.assign(base, st);
					this.setFeatureStyle(featureId, active);
				}
			})
			.on('dblclick', (e) => {
				this._propagateEvent(onDblclick, e);
				this.clearActive();
			});
	}

	componentDidMount() {
		const {
			layerContainer
		} = this.props.leaflet || this.context;
		const {
			tooltipClassName = '', tooltip = null, popup = null
		} = this.props;
		this.leafletElement.addTo(layerContainer);
		// bind tooltip
		if (tooltip) {
			this.leafletElement.bindTooltip((layer) => {
				if (isFunction(tooltip)) {
					return tooltip(layer);
				} else if (isString(tooltip) && layer.properties.hasOwnProperty(tooltip)) {
					return layer.properties[tooltip];
				} else if (isString(tooltip)) {
					return tooltip;
				}
				return '';
			}, {
				sticky: true,
				direction: 'auto',
				className: tooltipClassName
			});
		}
		// bind popup
		if (popup) {
			this.leafletElement.bindPopup((layer) => {
				if (isFunction(popup)) {
					return popup(layer);
				} else if (isString(popup)) {
					return popup;
				}
				return '';
			});
		}
	}

	_getFeatureId(feature) {
		const {
			idField
		} = this.props;
		if (isFunction(idField)) {
			return idField(feature);
		} else if (isString(idField)) {
			return feature.properties[idField];
		}
	}

	_propagateEvent(eventHandler, e) {
		if (!isFunction(eventHandler)) return;
		const featureId = this._getFeatureId(e.layer);
		const feature = this.getFeature(featureId);
		const event = deepClone(e);
		const mergedEvent = Object.assign(event.target, {
			feature
		});
		eventHandler(event);
	}

	setFeatureStyle(id, style) {
		this.leafletElement.setFeatureStyle(id, style);
	}

	resetFeatureStyle(id) {
		this.leafletElement.resetFeatureStyle(id);
	}

	clearHighlight() {
		if (this.highlight && this.highlight !== this.active) {
			this.resetFeatureStyle(this.highlight);
		}
		this.highlight = null;
	}

	clearActive() {
		if (this.active) {
			this.resetFeatureStyle(this.active);
		}
		this.active = null;
	}

	getFeature(featureId) {
		const {
			data,
			idField
		} = this.props;
		if (isEmpty(data)) return {};
		const feature = data.features.find(({
			properties
		}) => properties[idField] === featureId);
		return deepClone(feature);
	}
}
*/

export default VectorTileLayer;
