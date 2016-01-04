from django import VERSION as DJANGO_VERSION
from django.db import models
from django.db.models import SubfieldBase
from django.utils.translation import ugettext_lazy as _
import six


def class_path(cls):
    return cls.__module__ + '.' + cls.__name__


class ClassField(
    models.Field if DJANGO_VERSION >= (1, 8)
    else six.with_metaclass(SubFieldBase, models.Field)
):
    """A field which can store and return a class.

    This is useful for improving models that have a 'type code smell'.
    Instead of sniffing the type code, the field can provide one of several
    instantiable classes that can have named methods.
    """

    description = _('Class Field')

    _south_introspects = True

    def get_internal_type(self):
        return "CharField"

    def __init__(self, *args, **kwargs):
        if 'choices' not in kwargs:
            kwargs['editable'] = False
        # BoundField will try to call a class
        if 'initial' in kwargs:
            initial = kwargs['initial']
            kwargs['initial'] = unicode(initial)
        kwargs.setdefault('max_length', 255)
        super(ClassField, self).__init__(*args, **kwargs)
        # flaw in django 'self._choices = choices or []'
        # this means we can't let choices be an empty list
        # that is added to after the field is created.
        if 'choices' in kwargs:
            self._choices = kwargs['choices']

    def get_prep_value(self, value):
        if isinstance(value, basestring):
            return value
        if value is None and self.null == True:
            return None
        if not isinstance(value, type):
            value = type(value)
            if self.choices:
                choice_dict = dict(self.choices)
                if value not in choice_dict:
                    raise TypeError(
                        u"%s is not a valid choice for %s. Valid choices are %s" % (
                            value,
                            self,
                            choice_dict.keys()
                        )
                    )
        return self.get_db_prep_value(value, connection=None)

    def get_db_prep_value(self, value, connection, prepared=False):
        """Accepts a string for convenience. String should be of the same format
        as that of the stored class paths.
        """
        if isinstance(value, basestring):
            return value
        return class_path(value)

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_prep_value(value)

    def to_python(self, value):
        """Returns a class
        """
        if value is None or value == '':
            return None
        if isinstance(value, basestring):
            if value.startswith("<class '"):
                value = value[len("<class '"):-len("'>")]
            try:
                module_path, class_name = value.rsplit('.', 1)
            except ValueError as value_error:
                value_error.message += unicode(value)
                raise
            if self.choices:
                for (choice, description) in self.choices:
                    if module_path == choice.__module__ and class_name == choice.__name__:
                        return choice
                raise ValueError("%s is not one of the choices of %s" % (value, self))
            else:
                imported = __import__(
                    module_path,
                    globals(),
                    locals(),
                    [str(class_name)],
                    0
                )
                return getattr(imported, class_name)
        else:
            if isinstance(value, basestring):
                for (choice, description) in self.choices:
                    if value == choice:
                        return choice
                raise ValueError("%s is not one of the choices of %s" % (value, self))
            else:
                return value

    def get_db_prep_lookup(self, lookup_type, value, connection=None, prepared=False):
        # We only handle 'exact' and 'in'. All others are errors.
        if lookup_type == 'exact':
            return [self.get_db_prep_save(value, connection=connection)]
        elif lookup_type == 'in':
            return [self.get_db_prep_save(v, connection=connection) for v in value]
        else:
            raise TypeError('Lookup type %r not supported.' % lookup_type)

    def formfield(self, **kwargs):
        if DJANGO_VERSION < (1, 9):
            if self._choices and 'choices' not in kwargs:
                choices = list()
                if self.null:
                    choices.append((None, '---------'))
                for Class, label in self._choices:
                    choices.append((self.get_prep_value(Class), label))
                kwargs['choices'] = choices
        return super(ClassField, self).formfield(**kwargs)
    
    def value_from_object(self, obj):
        """Returns the class path, otherwise BoundField will
        mistake the class for a callable and try to instantiate it.
        """
        return class_path(super(ClassField, self).value_from_object(obj))

    def get_prep_lookup(self, lookup_type, value):
        # We only handle 'exact' and 'in'. All others are errors.
        if lookup_type == 'exact':
            return self.to_python(value)
        elif lookup_type == 'in':
            return [self.to_python(v) for v in value]
        else:
            raise TypeError('Lookup type %r not supported.' % lookup_type)

    def from_db_value(self, value, expression, connection, context):
        return self.to_python(value)

