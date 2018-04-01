from functools import wraps

class ProxyMethod:
    name = None

    def __set_name__(self, cls, name):
        self.name = name

    def __get__(self, proxy, cls):
        def wrapper(*args, **kwargs):
            proxied_f = getattr(object.__getattribute__(proxy, '_obj'), self.name)
            result = proxied_f(*args, **kwargs)
            if isinstance(result, cls.proxy_cls):
                result = cls(result)
            return result
        return wrapper
    
delegate = ProxyMethod

        
class Proxy:
    proxy_cls = None
    
    def __init__(self, obj):
        object.__setattr__(self, '_obj', obj)
        
    __or__ = delegate()
    __gt__ = delegate()
    __rshift__ = delegate()
    __ge__ = delegate()
    __lt__ = delegate()
    __lshift__ = delegate()
    __len__ = delegate()
    __getitem__ = delegate()
    __str__ = delegate()
    __repr__ = delegate()
    __getattribute__ = delegate()
    __setattr__ = delegate()
