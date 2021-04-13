import React, { useState, useEffect } from 'react';
import DatePicker from "react-datepicker";

import "react-datepicker/dist/react-datepicker.css";

/**
 * Create initial stewardship from a list of datatypes
 */
function GetInitialStewardshipValue(datatypes) {
    return datatypes.reduce((stewardship, datatype) => {
        const value = datatype.type == "choice"
            ? datatype.choices[0]
            : datatype.type == "date"
            ? new Date()
            : null;

        stewardship[datatype.name] = value;
        return stewardship;
    }, {});
}


function StewardshipField(props) {
    const { type, name, choices, onChange, stewardship } = props

    if (type == "choice") {
        return (
            <select
                className="form-control"
                name={name}
                onChange={(e) => {
                    onChange(name, e.target.value);
                }}
            >{choices.map((value, i) => <option
                    value={value}
                    >{value}</option>)}
            </select>
        );
    } else if (type == "date") {
        return (
            <DatePicker
                className="form-control"
                selected={stewardship[name]}
                onChange={(e) => {
                    onChange(name, e);
                }}
            />
        );
    }
}


function StewardshipRow(props) {
    const { datatypes, updateTreeData, addStewardship } = props;
    const [ stewardship, setStewardship ] = useState(GetInitialStewardshipValue(datatypes));

    const onChange = (name, value) => {
        setStewardship({...stewardship, [name]: value})
    }

    return (
        <tr className="editrow">
            {datatypes.map((x, i) => (<td><StewardshipField
                key={`stewardship_${x.name}_${i}`}
                onChange={onChange}
                stewardship={stewardship}
                {...x} /></td>))}
            <td><a className="btn add-row" onClick={() => addStewardship(stewardship)}> + </a></td>
        </tr>)
    ;
}


// the stewardship rows meant for reading
function StewardshipRowReadOnly(props) {
    const { datatypes, stewardship, index, removeStewardship } = props;

    const formatValue = (value, type) => {
        if (type == "date") {
            return `${value.getDate()}/${value.getMonth() + 1}/${value.getFullYear()}`;
        }

        return value;
    }

    return (
        <tr className="editrow">
            {datatypes.map((x, i) => (<td>{formatValue(stewardship[x.name], x.type)}</td>))}
            <td><a className="btn add-row" onClick={() => removeStewardship(index)}> X </a></td>
        </tr>)
    ;
}


export function Stewardship(props) {
    const { collectionUdfKey, collectionUdf, updateTreeData, treeData } = props;
    const [rows, setRows] = useState([]);

    const [stewardships, setStewardships] = useState(treeData[collectionUdfKey] || []);
    const addStewardship = (s) => {
        setStewardships([...stewardships, s]);
    }

    useEffect(() => {
        updateTreeData(collectionUdfKey, stewardships);
    }, [stewardships]);

    const removeStewardship = (index) => {
        var _stewardships = [...stewardships];
        _stewardships.splice(index, 1);
        setStewardships(_stewardships);
    }

    const title = `${collectionUdf.model_type} ${collectionUdf.name}`;
    // this is a list of objects with type, name and maybe choices
    const datatypes = JSON.parse(collectionUdf.datatype);

    return (
        <div>
            <h4>{title}</h4>
            <table className="table table-hover">
                <tbody>
                <tr className="headerrow">
                    {datatypes.map((x, i) => (<th>{x.name}</th>))}
                    <th></th>
                </tr>
                <StewardshipRow
                    datatypes={datatypes}
                    updateTreeData={updateTreeData}
                    addStewardship={addStewardship}
                />
                {stewardships.map((x, i) => {
                    return <StewardshipRowReadOnly
                        removeStewardship={removeStewardship}
                        datatypes={datatypes}
                        stewardship={x}
                        index={i} />
                })}
                </tbody>
            </table>
        </div>
    );
}



