from django.db import models
from django.db.models import SubfieldBase
from django.utils.translation import ugettext_lazy as _


class ClassField(models.Field):
    __metaclass__ = SubfieldBase

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
        return unicode(value)

    def get_db_prep_value(self, value, connection, prepared=False):
        return "%s.%s" % (value.__module__, value.__name__)

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
                imported = __import__(module_path, globals(), locals(), [class_name], 0)
                return getattr(imported, class_name)
        else:
            if isinstance(value, basestring):
                for (choice, description) in self.choices:
                    if value == choice:
                        return choice
                raise ValueError("%s is not one of the choices of %s" % (value, self))
            else:
                return value

    def get_db_prep_lookup(self, lookup_type, value, connection=None):
        # We only handle 'exact' and 'in'. All others are errors.
        if lookup_type == 'exact':
            return [self.get_db_prep_save(value, connection=connection)]
        elif lookup_type == 'in':
            return [self.get_db_prep_save(v, connection=connection) for v in value]
        else:
            raise TypeError('Lookup type %r not supported.' % lookup_type)

    def formfield(self, **kwargs):
        if self._choices and 'choices' not in kwargs:
            kwargs['choices'] = list((self.get_prep_value(Class), label) for Class, label in self._choices)
        return super(ClassField, self).formfield(**kwargs)
    
    def value_from_object(self, obj):
        """Returns the unicode name of the class, otherwise BoundField will
        mistake the class for a callable and try to instantiate it.
        """
        return unicode(super(ClassField, self).value_from_object(obj))
