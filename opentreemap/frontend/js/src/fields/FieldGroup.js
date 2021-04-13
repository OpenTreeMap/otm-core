import React, { useEffect, useRef, useState, useMemo } from 'react';

import { Stewardship } from './Stewardship';
import DatePicker from "react-datepicker";


export function FieldGroup(props) {
    const { errors, fieldGroup, filterFields, updateTreeData, treeData } = props;
    return (
        <>
        <h3>{fieldGroup.header}</h3>
        <FieldTable
            updateTreeData={updateTreeData}
            treeData={treeData}
            errors={errors}
            fields={fieldGroup.fields.filter(x => filterFields.indexOf(x.identifier) == -1)} />
        <hr />
        {fieldGroup.collection_udf_keys.map((c, i) => [c, fieldGroup.collection_udfs[i]])
            .map((c,i) => <Stewardship
                key={`${c[0]}.${i}`}
                updateTreeData={updateTreeData}
                treeData={treeData}
                collectionUdfKey={c[0]}
                collectionUdf={c[1]}
            />)
        }
        </>
    );
}


export function Field(props) {
    const {
        data_type,
        choices,
        units,
        identifier,
        //value,
        updateTreeData,
        treeData } = props;

    const value = treeData[identifier] || "";

    var input = null;
    if (data_type == "bool") {
        input = (<input
            type="checkbox"
            name={identifer}
            checked={value || false}
            onClick={(e) => updateTreeData(identifier, e.target.value)}
        />);
    }
    else if (choices?.length > 0) {
        const multiple = data_type == "multichoice"
            ? {"multiple": "multiple"}
            : {};
        // FIXME add selected
        input = (<select
            name={identifier}
            value={value || ""}
            onChange={(e) => updateTreeData(identifier, e.target.value)}
            className="form-control">
            {choices.map((option, i) => <option
                value={option.value}
                >{option.display_value}</option>)}
        </select>);
    }
    else if (data_type == "date" || data_type == "datetime") {
        // FIXME add a datepicker
        const startDate = new Date();
        input = (<DatePicker
            selected={value}
            startDate={startDate}
            onChange={(e) => {
                updateTreeData(identifier, e);
            }}
            dateFormat="yyyy-MM-dd"
            />);
    }
    else if (data_type == "long_string") {
        input = (<textarea
            name={identifier}
            className="form-control"
            onChange={(e) => updateTreeData(identifier, e.target.value)}
            value={value || ''} />);
    }
    else if (units) {
        input = (
            <div className="input-group">
                <input
                    name={identifier}
                    className="form-control"
                    onChange={(e) => updateTreeData(identifier, e.target.value)}
                    value={value || ''}/>
                <div className="input-group-append">
                    <span className="input-group-text">{units}</span>
                </div>
            </div>);
    } else {
        input = (<input
            name={identifier}
            type="text"
            onChange={(e) => updateTreeData(identifier, e.target.value)}
            className="form-control" />);
    }

    return (
        <div className="input-group">{input}</div>
    );
}


function FieldRow(props) {
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
        value,
        errors,
        updateTreeData,
        treeData } = props;

    return (
        <tr className={errors != null ? "alert-danger" : ''}>
            <td>{is_editable && is_required
                ? '* ' : ''}{label}
                {errors != null ? <ValidationError message={errors[0]} /> : ''}
            </td>
            {is_editable
                ? <td><Field {...props} /></td>
                : ''
            }
        </tr>
    );
}


function ValidationError(props) {
    return (
        <div className="alert-danger text-info"><i>{props.message}</i></div>
    );
}


function FieldTable(props) {
    const { errors, fields, updateTreeData, treeData } = props;

    return (
        <table className="table table-hover">
            <tbody>
            {fields
                .filter(x => x.is_visible)
                .map((field, i) => {return (
                    <>
                    <FieldRow
                        key={i}
                        updateTreeData={updateTreeData}
                        treeData={treeData}
                        errors={errors ? errors[field.identifier] : null}
                        {...field} />
                    </>
                )})
            }
            </tbody>
        </table>
    );
}


/**
 * Display a field with a label and value, with optional units
 */
export function FieldReadOnly(props) {
    const { label, units, value } = props;

    // round to 1 decimal place if this is a number
    const valueFormatted = typeof(value) === 'number'
        ? (Math.round(value * 10) / 10).toFixed(1)
        : value;

    const valueLabel = units != null
        ? `${valueFormatted} ${units}`
        : `${valueFormatted}`;

    return (
        <div className="form-group">
            <label>{label}</label>
            <div className="field-view"> {valueLabel} </div>
        </div>
    );
}
