class DotDict(dict):
    """
    Dictionary class supporting keys like "a.b.c" for nested dictionaries
    From http://stackoverflow.com/questions/3797957 (RM added get())

    Supports get() with a dotted key and a default, e.g.
        config.get('fruit.apple.type', 'delicious')
    as well as creating dotted keys when no keys in the path exist yet, e.g.
        config = DotDict({})
        config.fruit.apple.type = 'macoun'
    """
    def __init__(self, value=None):

        if value is None:
            pass
        elif isinstance(value, dict):
            for key in value:
                self.__setitem__(key, value[key])
        else:
            raise TypeError('Expected dict')

    def _ensure_dot_dict(self, target, restOfKey, myKey):
        if not isinstance(target, DotDict):
            raise KeyError('Cannot set "%s" in "%s" (%s)' %
                           (restOfKey, myKey, repr(target)))

    def __setitem__(self, key, value):
        if '.' in key:
            myKey, restOfKey = key.split('.', 1)
            target = self.setdefault(myKey, DotDict())
            self._ensure_dot_dict(target, restOfKey, myKey)
            target[restOfKey] = value
        else:
            if isinstance(value, dict) and not isinstance(value, DotDict):
                value = DotDict(value)
            dict.__setitem__(self, key, value)

    def __getitem__(self, key):
        if '.' not in key:
            return dict.__getitem__(self, key)
        myKey, restOfKey = key.split('.', 1)
        target = dict.__getitem__(self, myKey)
        self._ensure_dot_dict(target, restOfKey, myKey)
        return target[restOfKey]

    def get(self, key, default=None):
        if '.' not in key:
            return dict.get(self, key, default)
        myKey, restOfKey = key.split('.', 1)
        if myKey not in self:
            return default
        target = dict.__getitem__(self, myKey)
        self._ensure_dot_dict(target, restOfKey, myKey)
        return target.get(restOfKey, default)

    def __contains__(self, key):
        if '.' not in key:
            return dict.__contains__(self, key)
        myKey, restOfKey = key.split('.', 1)
        target = dict.__getitem__(self, myKey)
        if not isinstance(target, DotDict):
            return False
        return restOfKey in target

    def setdefault(self, key, default):
        if key not in self:
            self[key] = default
        return self[key]

    __setattr__ = __setitem__
    __getattr__ = __getitem__
