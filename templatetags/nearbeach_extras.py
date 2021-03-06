import datetime, pytz
from django.utils import timezone
from django.conf import settings
from django.template import Library
register = Library()


@register.filter(name='filter_level_cards')
def filter_level_cards(value, arg):
    """
    :param value: this is the python object being passed through
    :param arg: these are the co-ordinates [column,level]
    :return: the filtered python object
    """
    return value.filter(kanban_level=arg)


@register.filter(name='filter_column_cards')
def filter_column_cards(value, arg):
    """
    :param value: this is the python object being passed through
    :param arg: these are the co-ordinates [column,level]
    :return: the filtered python object
    """
    return value.filter(kanban_column=arg)

@register.filter
def hours_ago(time, hours):
    """
    :param time:
    :param hours:
    :return:
    """
    location = pytz.timezone(settings.TIME_ZONE)
    local_time = location.localize(datetime.datetime.now())

    try:
        return local_time - time > -datetime.timedelta(hours=hours)
    except:
        return datetime.datetime.now() - time > -datetime.timedelta(hours=hours)
