import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Accordion, Card, useAccordionToggle } from 'react-bootstrap';

export function EcobenefitsSideBar(props) {
    const { benefits, onToggleClick } = props;
    const [expanded, setExpanded] = useState(false);
    //const instance_url = window.django.instance_url;
    //const [benefits, setBenefits] = useState(null);

    /*
    useEffect(() => {
        // clear the title before loading a new one
        var url = `/${instance_url}/benefit/search/api`;
        axios.get(url, {withCredential: true})
            .then(res => {
                setBenefits(res.data);
                console.log(res);
            }).catch(res => {
                console.log('error');
                console.log(res);
            });
    }, []);
    */

    if (benefits == null) return "Loading..";

    return (
        <div id="sidebar-browse-trees">
            <div className="panel">
                <div className="panel-group">
                    <div className="panel-heading">
                        <a className="panel-toggle">
                            Detail / Eco Benefits
                            <span className="arrow pull-right">
                                <i className="icon-right-open"></i>
                            </span>
                        </a>
                    </div>
                    <div className="collape in panel-body">
                        <EcobenefitsPanel benefits={benefits} onToggleClick={onToggleClick} />
                    </div>
                </div>
            </div>
        </div>
    );
}

export function EcobenefitsPanel(props) {
    const { benefits, basis, onToggleClick } = props;
    if (benefits == null) return (<div></div>);

    return (
        <div className="panel-body">
            <div className="panel-inner benefit-values">
                <a
                    className="sidebar-panel-toggle visible-xs-block d-block d-sm-none"
                    onClick={() => onToggleClick()}
                >
                    <i className="icon-right-open"></i>
                </a>
                <BenefitRow isTotal={true} {...benefits.all.totals} />
                <div className="benefit-value-title">Tree Benefits</div>
                {Object.values(benefits.plot).map((x, i) => {
                    return <BenefitRow key={i} {...x} />;
                })}
                <div className="benefit-tree-count">
                    Based on {basis?.plot?.n_objects_used?.toLocaleString()} out of {basis?.plot?.n_total.toLocaleString()} total trees.
                </div>
            </div>
        </div>
    );

}

function BenefitRow(props){
    const iconClass = props.icon != null ? `icon-${props.icon}` : "icon-sun-filled";
    var benefitContent = null;
    if (props.value != null) {
        benefitContent = `${props.value} ${props.unit}`;
        if (props.currency_saved) {
            benefitContent += ` saved ${props.currency_saved}`;
        }
    } else if (props.currency_saved) {
        benefitContent = `${props.currency_saved} saved`;
    }

    if (benefitContent == null) return "";
    return (
        <div className={`benefit-value-row ${props.isTotal ? 'benefit-total' : ''}`}>
            <div className="benefit-icon"><i className={iconClass} /></div>
            <h3 className="benefit-label">{props.label}</h3>
            <span className="benefit-content">
                {benefitContent}
            </span>
        </div>
    );
}
