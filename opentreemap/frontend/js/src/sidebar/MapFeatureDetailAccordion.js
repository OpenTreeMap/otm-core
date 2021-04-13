import React, { useEffect, useRef, useState, useMemo } from 'react';
import { Accordion, Card, useAccordionToggle } from 'react-bootstrap';

import reverse from 'reverse';

import { SpeciesTitle } from '../fields/Species';
import { EcobenefitsPanel } from './EcobenefitsSideBar';
import { DiameterReadOnly } from '../fields/Diameter';
import { FieldReadOnly } from '../fields/FieldGroup';


export function MapFeatureDetailAccordion(props) {
    const { benefits, tree, feature, plot, units, onToggleClick } = props;

    const featureUrl = reverse.Urls.map_feature_detail({
        instance_url_name: window.django.instance_url,
        feature_id: feature.id
    });

    //<a className="btn" id="full-details-btn" href={featureUrl}>More Details</a>

    return (<div className="panel-body">
        <div className="panel-body-buttons-wrapper">
            <div className="panel-body-buttons">
                <a className="btn" id="full-details-btn" href={featureUrl}>More Details</a>
            </div>
        </div>
        <div className="panel-inner" onClick={() => onToggleClick()}>
            <Accordion.Toggle
                as={Card.Header}
                className="visible-xs-block feature-info d-block d-sm-none"
                onClick={() => onToggleClick()}
            >
                <h4>{tree.species.common_name}</h4>
            </Accordion.Toggle>

            <form id="details-form">
                <SpeciesTitle
                    commonName={tree.species.common_name}
                    scientificName={tree.species.scientific_name}
                />

                <FieldReadOnly
                    label={"Trunk Diameter"}
                    units={units['tree.diameter']}
                    value={tree.diameter} />
                <FieldReadOnly
                    label={"Tree Height"}
                    units={units['tree.height']}
                    value={tree.height} />

                <EcobenefitsPanel benefits={benefits} />
            </form>
        </div>

    </div>);
}
