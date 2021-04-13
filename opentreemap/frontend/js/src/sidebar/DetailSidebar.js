import React, { useEffect, useRef, useState } from 'react';
import { Accordion, Card, useAccordionToggle } from 'react-bootstrap';
import axios from 'axios';

import { EcobenefitsPanel } from './EcobenefitsSideBar';
import { MapFeatureDetailAccordion } from './MapFeatureDetailAccordion';


export function DetailSidebar(props) {
    const { benefits, sidebarInfo, map, addSelectedMarkerInfo } = props;
    const accordionRef = useRef(null);

    const [activeId, setActiveId] = useState('1');
    const [expandedDetails, setExpandedDetails] = useState(false);
    const [expandedBenefits, setExpandedBenefits] = useState(false);

    // to keep track of previous center for expanding and collapsing
    const [mapCenter, setMapCenter] = useState(false);

    useEffect(() => {
        const ac = accordionRef;
        setActiveId(sidebarInfo != null
            ? '0'
            : '1'
        );
        setExpandedDetails(false);
        setExpandedBenefits(false);
    }, [sidebarInfo]);

    const toggleActiveId = (id) => {
        setActiveId(id == activeId
            ? null
            : id
        );
    }

    const toggleExpandedDetails = () => {
        var expandedDetailsNew = !expandedDetails;
        var newMapCenter = null;
        if (expandedDetailsNew){
            // save the previous center, move to this data point
            setMapCenter(map.getCenter());
            newMapCenter = addSelectedMarkerInfo.latLng;
            document.body.classList.add('open');
            document.body.classList.add('hide-search');
        } else {
            newMapCenter = mapCenter;
            setMapCenter(null);
            document.body.classList.remove('open');
            document.body.classList.remove('hide-search');
        }

        setExpandedDetails(expandedDetailsNew);

        setTimeout(() => {
            map.invalidateSize();
            map.panTo(
                newMapCenter, {
                    animate: true,
                    duration: 0.4,
                    easeLinearity: 0.1
                });
        }, 500);
    }

    const toggleExpandedBenefits = () => {
        var expandedBenefitsNew = !expandedBenefits;
        if (expandedBenefitsNew){
            document.body.classList.add('open');
            document.body.classList.add('hide-search');
        } else {
            document.body.classList.remove('open');
            document.body.classList.remove('hide-search');
        }

        setExpandedBenefits(expandedBenefitsNew);
    }

    return (<>
        <Accordion defaultActiveKey={activeId} className="panel" ref={accordionRef} activeKey={activeId}>
            <Card className={`panel-group ${expandedDetails ? 'expanded with-map' : ''}`}>
                <Accordion.Toggle
                    as={Card.Header}
                    onClick={() => toggleActiveId('0')}
                    eventKey="0"
                    className="panel-heading"
                >
                    <a className="panel-toggle">
                        Details
                        <span className="arrow pull-right">
                            <i className="icon-right-open"></i>
                        </span>
                    </a>
                </Accordion.Toggle>
                <Accordion.Collapse
                    eventKey="0"
                    className=""
                >
                {sidebarInfo != null
                    ? <MapFeatureDetailAccordion
                        onToggleClick={() => toggleExpandedDetails()}
                        {...sidebarInfo}
                        />
                    : <div></div>
                }
                </Accordion.Collapse>
            </Card>
            <Card className={`panel-group ${expandedBenefits ? 'expanded' : ''}`}>
                <Accordion.Toggle
                    as={Card.Header}
                    eventKey="1"
                    className="panel-heading"
                    onClick={() => toggleActiveId('1')}
                >
                    <a className="panel-toggle">
                        Eco Benefits
                        <span className="arrow pull-right">
                            <i className="icon-right-open"></i>
                        </span>
                    </a>
                </Accordion.Toggle>
                <Accordion.Collapse
                    eventKey="1"
                >
                    <EcobenefitsPanel
                        benefits={benefits?.benefits}
                        basis={benefits?.basis}
                        onToggleClick={() => toggleExpandedBenefits()}
                    />
                </Accordion.Collapse>
            </Card>
        </Accordion>
    </>);
}
