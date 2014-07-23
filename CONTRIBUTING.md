# Contributing

## Architecture

This section addresses the question of where code should live.

### Permissions

Because of the complicated relationship of models associated with permission checking, permissions are centralized in a module, `treemap/lib/perms.py`, instead of added as methods to a class. Functions that check permissions should be written to accept a number of related types or type combinations and stored in this module. The private functions in this module should be responsible for walking the necessary relationships in order to check the permission properly.

