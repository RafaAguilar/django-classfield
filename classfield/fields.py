from django import VERSION as DJANGO_VERSION
from django.db import models
from django.db.models import SubfieldBase
from django.utils.translation import ugettext_lazy as _
from django.forms.fields import ChoiceField
import six


def class_path(cls):
    return cls.__module__ + '.' + cls.__name__


class FakeType(type):
    def __nonzero__(cls):
        return False


class FakeModel(six.with_metaclass(FakeType, object)):
    class _meta:
        concrete_fields = []
        fields = []
        app_label = 'ClassField'
        model_name = 'ClassFields FakeModel'


class ClassFieldFakeRemoteField(object):
    """Make this look a bit like a ForeignKey (but not).
    Workaround for bug in SQLUpdateCompiler.as_sql()
    """
    model = FakeModel
    parent_link = True


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
    
    rel = None

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
        # Workaround for a bug in django 1.9
        # in SQLUpdateCompiler.as_sql, it prohibits setting
        # anything with a prepare_database_save() method on a
        # field that has no remote_field.
        # That's silly, it should let the field control this.
        self.remote_field = ClassFieldFakeRemoteField()
        self.db_constraint = None

    def get_prep_value(self, value):
        if isinstance(value, str):
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
        if isinstance(value, str):
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
        if isinstance(value, str):
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
            if isinstance(value, str):
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
        if self._choices and 'choices' not in kwargs:
            choices = list()
            if self.null:
                choices.append((None, '---------'))
            for Class, label in self._choices:
                choices.append((self.get_prep_value(Class), label))
            kwargs['choices'] = choices
            if DJANGO_VERSION >= (1, 9):
                return super(ClassField, self).formfield(
                    form_class=ChoiceField,
                    **kwargs
                )
        return super(ClassField, self).formfield(
            **kwargs
        )
    
    def value_from_object(self, obj):
        """Returns the class path, otherwise BoundField will
        mistake the class for a callable and try to instantiate it.
        """
        if obj is None:
            return None
        else:
            super_value = super(ClassField, self).value_from_object(obj)
            if super_value:
                return class_path(super_value)
            else:
                return None

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


class PrepareDatabaseSaveDescriptor(object):
    """A descriptor to work around a flaw in django;

    SQLUpdateCompiler.as_sql() calls model.prepare_database_save if value has
    this method (ideally it should let the field decide).

    Plus we encounter a bug in python itself;
      (class methods names clash with instance method names)

    Therefore a descriptor is appropriate, pythonic workaround, but
    better if the django flaw is fixed.
    """
    def __get__(self, obj, type=None):
        # return appropriate method based on instance or class:
        if obj is None:
            def class_prepare_database_save(field):
                return field.get_prep_value(type)
            return class_prepare_database_save
        else:
            def object_prepare_database_save(field):
                return super(Token, obj).prepare_database_save(field)
            return object_prepare_database_save
