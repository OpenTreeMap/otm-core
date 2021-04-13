import { Button, Form, Table } from 'react-bootstrap';
import { useTable, useSortBy, useGlobalFilter, usePagination } from 'react-table';


export const ReactTable = ({columns, data}) => {

    const filterTypes = {
        text: (rows, id, filterValue) => {
            return rows.filter(row => {
            const rowValue = row.values[id];
            return rowValue !== undefined
                ? String(rowValue)
                    .toLowerCase()
                    .startsWith(String(filterValue).toLowerCase())
                : true;
            });
        }
    };

    const {
        getTableProps,
        getTableBodyProps,
        headerGroups,
        rows,
        prepareRow,
        page,
        canPreviousPage,
        canNextPage,
        pageOptions,
        pageCount,
        gotoPage,
        nextPage,
        previousPage,
        setPageSize,
        setGlobalFilter,
        visibleColumns,
        state: { pageIndex, pageSize, globalFilter },
    } = useTable({
            columns,
            data,
            initialState: { pageIndex: 0 }
        },
        useGlobalFilter,
        useSortBy,
        usePagination
    );

    return (
        <div>
            <div
                className="p-1 border-0 d-flex justify-content-end"
                colSpan={visibleColumns.length}
            >
                <GlobalFilter
                    globalFilter={globalFilter}
                    setGlobalFilter={setGlobalFilter}
                />
            </div>

            <Table striped bordered hover {...getTableProps()}>
                <thead>
                    {headerGroups.map(headerGroup => (
                        <tr {...headerGroup.getHeaderGroupProps()}>
                            {headerGroup.headers.map(column => {
                                const {render, getHeaderProps} = column;
                                return (
                                    <th {...getHeaderProps()}>{render("Header")}</th>
                                )
                            })}
                        </tr>
                    ))}
                </thead>
                <tbody {...getTableBodyProps()}>
                    {page.map((row, i) => {
                        prepareRow(row);
                        return (
                            <tr {...row.getRowProps()}>
                                {row.cells.map(cell => {
                                    return (
                                        <td {...cell.getCellProps()}>{cell.render("Cell")}</td>
                                    );
                                })}
                            </tr>
                        );
                    })}
                </tbody>
            </Table>
            <div>
                <Button onClick={() => gotoPage(0)} disabled={!canPreviousPage}>{"<<"}</Button>{" "}
                <Button onClick={() => previousPage()} disabled={!canPreviousPage}> {"<"} </Button>{" "}
                <Button onClick={() => nextPage()} disabled={!canNextPage}> {">"} </Button>{" "}
                <Button onClick={() => gotoPage(pageCount - 1)} disabled={!canNextPage}> {">>"} </Button>{" "}
                <span> Page{" "} <strong> {pageIndex + 1} of {pageOptions.length} </strong>{" "} </span>
                <span>
                    | Go to page:{" "}
                    <input
                        type="number"
                        defaultValue={pageIndex + 1}
                        onChange={e => {
                            const page = e.target.value ? Number(e.target.value) - 1 : 0;
                            gotoPage(page);
                        }}
                        style={{ width: "100px" }}
                    />
                </span>{" "}
                <select
                    value={pageSize}
                    onChange={e => {
                        setPageSize(Number(e.target.value));
                    }}
                    > {[10, 20, 30, 40, 50].map(pageSize => (
                        <option key={pageSize} value={pageSize}>
                            Show {pageSize}
                        </option>
                    ))}
                </select>
            </div>
        </div>
    );
}


const GlobalFilter = ({ globalFilter, setGlobalFilter }) => {
    return (
        <CustomImport
            value={globalFilter || ""}
            onChange={e => {
                setGlobalFilter(e.target.value || undefined)
            }}
            placeholder="Search all..."
        />
    );
}


const CustomImport = props => {

  let { placeholder, name, value, onChange = () => null } = props;

  return (
    <Form.Group>
      <Form.Control
        placeholder={placeholder}
        name={name}
        value={value ? value : ""}
        onChange={onChange}
      />
    </Form.Group>
  );
};


export default ReactTable;
