import React, { useEffect, useRef, useState, useMemo } from 'react';


function DiameterCalculator(props) {
    const {
        value,
        digits,
        units,
        identifier,
        updateTreeData,
        treeData } = props;
    const [ diameter, setDiameter ] = useState(treeData[identifier] || null);
    const [ circumference, setCircumference ] = useState(null);

    const onDiameterChange = (e) => {
        const value = e.target.value;
        setDiameter(value);

        const circumference = Math.round(value * Math.PI * 100) / 100;
        setCircumference(circumference);

        updateTreeData(identifier, value);
    }

    const onCircumferenceChange = (e) => {
        const value = e.target.value;
        setCircumference(value);

        const diameter = Math.round(value / Math.PI * 100) / 100;
        setDiameter(diameter);

        updateTreeData(identifier, diameter);
    }

    return (
        <>
        <table id="diameter-calculator" className="table table-hover table-bordered">
        <thead>
            <tr>
            <th>Diameter</th>
            <th>Circumference</th>
            </tr>
        </thead>
        <tbody id="diameter-worksheet">
            <tr id="trunk-row">
            <td>
                <div className="input-group">
                <input
                    className="input-sm form-control"
                    name="diameter"
                    type="text"
                    value={diameter}
                    onChange={onDiameterChange}
                    />
                <div className="input-group-append">
                    <span className="input-group-text">{units}</span>
                </div>
                </div>
            </td>
            <td>
                <div className="input-group">
                <input
                    className="input-sm form-control"
                    name="circumference"
                    type="text"
                    value={circumference}
                    onChange={onCircumferenceChange}
                    />
                <div className="input-group-append">
                    <span className="input-group-text">{units}</span>
                </div>
                </div>
            </td>
            </tr>
        </tbody>
        <tfoot>
            <tr>
            <td colspan="2">
                <a id="add-trunk-row">Add another trunk?</a>
            </td>
            </tr>
        </tfoot>
        </table>
        <p id="diameter-calculator-total-row" style={{display: 'none'}}>
        Combined Diameter:<span id="diameter-calculator-total-reference" className="inline"></span>{units ? units : ''}
        </p>
        </>
    );
}

export function Diameter(props) {
    const {
        choices,
        length,
        data_type,
        digits,
        display_value,
        explanation,
        identifier,
        is_editable,
        is_required,
        is_visible,
        label,
        units,
        errors,
        value } = props;

    return (
        <div className={`form-group ${errors != null ? 'alert-danger' : ''}`}>
            <label>* {label}</label>
            {is_editable
                ? <div className="field-edit"><DiameterCalculator {...props} /></div>
                : ''}
            {explanation
                ? <p className="explanation">{explanation}</p>
                : ''}
            {errors != null
                ? <div className="alert alert-danger text-info">{errors[0]}</div>
                : ''
            }
        </div>
    );
}

export function DiameterReadOnly(props) {
    const { units, value } = props;

    const valueLabel = units != null
        ? `${value} ${units}`
        : `${value}`;

    return (
        <div className="form-group">
            <label>Trunk Diameter</label>
            <div className="field-view"> {valueLabel} </div>
        </div>
    );
}
