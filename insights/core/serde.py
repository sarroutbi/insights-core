import json as ser
import logging
import os

from insights.core import dr
from insights.util import fs

log = logging.getLogger(__name__)

SERIALIZERS = {}
DESERIALIZERS = {}


def serializer(_type):
    """ Decorator for serializers."""

    def inner(func):
        if _type in SERIALIZERS:
            msg = "%s already has a serializer registered: %s"
            raise Exception(msg % (dr.get_name(_type), dr.get_name(SERIALIZERS[_type])))
        SERIALIZERS[_type] = func
        return func
    return inner


def deserializer(_type):
    """ Decorator for deserializers."""

    def inner(func):
        if _type in DESERIALIZERS:
            msg = "%s already has a deserializer registered: %s"
            raise Exception(msg % (dr.get_name(_type), dr.get_name(DESERIALIZERS[_type])))
        DESERIALIZERS[_type] = func
        return func
    return inner


def get_serializer(obj):

    """ Get a registered serializer for the given object.

        This function walks the mro of obj looking for serializers.
        Returns None if no valid serializer is found.
    """
    _type = type(obj)
    for o in _type.mro():
        if o not in SERIALIZERS:
            continue
        return lambda x: {"type": dr.get_name(_type), "object": SERIALIZERS[o](x)}
    return lambda x: {"type": None, "object": x}


def get_deserializer(obj):
    """ Returns a deserializer based on the fully qualified name string."""
    for o in obj.mro():
        if o in DESERIALIZERS:
            return DESERIALIZERS[o]


def serialize(obj):
    to_dict = get_serializer(obj)
    return to_dict(obj)


def deserialize(data):
    if not data.get("type"):
        return data["object"]

    _type = dr.get_component(data["type"])
    if not _type:
        raise Exception("Unrecognized type: %s" % data["type"])

    to_obj = get_deserializer(_type)
    if not to_obj:
        raise Exception("No deserializer for type: %s" % data["type"])

    return to_obj(_type, data["object"])


def persister(output_dir, ignore_hidden=True):
    def observer(c, broker):
        log.debug("Firing for %s!" % dr.get_name(c))
        if c not in broker:
            log.debug("Not in broker %s!" % dr.get_name(c))
            return

        if ignore_hidden and dr.is_hidden(c):
            return

        value = broker[c]
        if isinstance(value, list):
            content = [serialize(t) for t in value]
        else:
            content = serialize(value)
        name = dr.get_name(c)
        doc = {}
        doc["name"] = name
        doc["time"] = broker.exec_times[c]
        doc["results"] = content
        path = os.path.join(output_dir, name + "." + dr.get_simple_module_name(ser))
        try:
            with open(path, "wb") as f:
                ser.dump(doc, f)
        except Exception as boom:
            log.exception(boom)
            fs.remove(path)

    return observer


def hydrate(payload):
    key = dr.get_component(payload["name"])
    data = payload["results"]
    try:
        value = [deserialize(d) for d in data]
    except:
        value = deserialize(data)

    return (key, value)
