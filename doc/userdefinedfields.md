# User Defined Fields

## Goals

### Scalar Data Fields

Attach arbitrary pieces of data to models. For instance, we may want to
assign a 'planting date' to a tree. This field should appear like a
normal field to the end user and also participate in the audit trail as
normally as possible.

These fields also work with the 'authorizable' trait to allow admins to
determine who is allowed to edit and update it.

For instance, if 'planting date' were added to a tree and a user changed
it the audit trail would look like:

> User 'Joe' updated Tree 482, add 'stewardship' (UDF)
> User 'Joe' updated Tree 482, set 'action' to 'watered'
> User 'Joe' updated Tree 482, set 'user' to 'joe'
> User 'Joe' updated Tree 482, set 'date' to '3/3/2003'


### Collection Fields

Besides simple data users should also be able to store multiple
rows. For instance, an admin should be able to add a field called
'Watered' that allows a user to note when a tree was watered and who did
the watering.

In this case, an audit trail would look something like:

> User 'Joe' updated Tree 482, 'watered' on '3/3/2003'

These fields should also participate in the authorizable
system.

## Scalar Implementation

For Scalar UDFs we can stick them directly on the model in a
'udf_scalar_values' field using an hstore.

The 'field id' parameter comes from a 'Field Definition' table:

```
User Defined Field Definition
id         - primary key
model_type - 'Plot' | 'Tree'
datatype   - ('int'
              | 'float'
              | 'string'
              | 'date'
              | 'user'
              | 'choice') ':' (name of field)
extra      - JSON metadata about the field, such as validations or
             choices
ismulti    - True if this UDF can have multiple rows
name       - String representation of the field name
```

These fields can act like normal auditable and authoriable fields by
simply being included as attributes and overriding the ```_dict```
method and the ```_previous_state``` variables.

This means that changing 'date_planted' to '3/3/2003' will result in an
audit record:

```
Audit
model          - 'Tree'
model_id       - 4442
field          - 'Date Planted'
previous_value - <null>
current_value  - '3/3/2003'
user           - 'Joe'
```

And that 'FieldPermission' objects can be created for the field 'date planted'

## Collection Implementation

Collection objects can be stored simply as 'hstores' in their own
table. They share the UDFD table and are delimited by `ismulti=True`.

The datatable:

```
Collection User Defined Field Value
id        - primary key
data      - hstore
field_def - Foreign Key to UDFD
model_id  - Foreign key to the model's table
```

When a Collection User Defined Field Value record is added a
'pseudo model' is used, based on the UDFD's id. In this case,
if a UDFD was defined as:

```
model    - 'Plot'
datatype - ['date:waterdate','user:wateruser']
ismulti  - True
name     - 'Watered at:'
id       - 1
```

Adding a new 'Watered at' event would result in an audit record similar
to:

```
Audit
model          - 'UDF:1'
model_id       - 4442
action         - 'Insert'
user           - 'Joe'
```

## Searching

Searching for simple UDFs can be done using the normal json query syntax
and making minor changes to the SQL query.

If there was a UDF called 'planting user' the query could look like:

```
{'tree.udf.planting_user': {'IS': 5}}
```

```sql
SELECT * FROM treemap_tree WHERE udf_scalar_values->planting_user = '5';
```

Searching in multi-row situations becomes a bit harder. Using the
'watered at' example about we may want to search for all trees that
haven't been watered for a week (assume that 5/5/2005 was a week ago).

```
{'tree.udf.watered_at.waterdate': {'LT': '5/5/2005'}}
```

These can be implemented using a subquery:


```
SELECT * FROM treemap_tree
WHERE id in (select model_id
  FROM udf_collection_value_data
  WHERE
     AND MAX(data->waterdate) < '5/5/2005'
     AND field_def=44
  GROUP BY model_id)
```
