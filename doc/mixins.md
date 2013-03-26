Mixins
======

This file provides high level documentation about the model
mixins included in the treemap application.  

treemap/audits.py provides the classes ```Authorizable```, ```Auditable```,
which are intended to be used as mixins to Django models using
multiple inheritance.  

Basic usage is as follows:  
```class Foo(Authorizable, Auditable, models.Model)```  
```class Foo(Authorizable, models.Model)```  
```class Foo(Auditable, models.Model)```  
```class Foo(Auditable, Authorizable, models.Model)``` **  

** This inheritance order has been tested, but is not recommended.  

Both of these classes involve coupling a specific user with an
action on the model, which is why the standard ```save()``` and ```delete()```
methods have been disallowed. Instead, you must use ```save_with_user(user)``` 
and ```delete_with_user(user)```.

The custom methods provided by these classes can pass through to other
class' methods, so that ```Authorizable.save_with_user``` will call 
```Auditable.save_with_user``` if it is further right in the inheritance order
and they can be expected to 'just work'.

Authorizable
------------

Authorizable provides a number of methods and internal properties
to manage access to model fields for individual users.  

Methods like ```_user_can_create``` and ```user_can_delete``` are used to determine
if a user is authorized, and these methods are called from the ```save_with_user```
and ```delete_with_user``` methods.  

Authorizable provides a ```clobber_unauthorized()``` method which takes a user 
and deletes the field values that the user does not have access to. The idea
is to use this method to sanitize an object before using it in a template. 
Internally, the model maintains state about whether clobbering has taken 
place. If clobbering has occurred, then certain key actions become disallowed,
like ```save_with_user``` and ```delete_with_user```.  

Auditable
---------

Auditable provides methods that create an audit record for every CRUD transaction
that takes place on a model. Depending on a user's permission level, the audit
is submitted for review before, or after, the transaction actually takes place.  

