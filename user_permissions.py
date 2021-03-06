"""
This python script will return the user's permission level for ANY given permission
"""
import json
from .models import *
from django.db.models import Max
from django.http import HttpResponseRedirect
from django.urls import reverse


def return_user_permission_level(request, group_list,permission_field):
    """

    :param request:
    :param group: limits data to a certain group - Null if no group
    :param permission_field: which permission field we will be looking at. The available list is;
        permission_set_id
        permission_set_name
        administration_assign_users_to_groups
        administration_create_groups
        administration_create_permission_sets
        administration_create_users
        assign_campus_to_customer
        associate_project_and_tasks
        customer
        invoice
        invoice_product
        opportunity
        organisation
        organisation_campus
        project
        quote
        requirement
        requirement_link
        task
        document
        contact_history
        project_history
        task_history

        Please note - if you want to look up more than ONE permission, please include them in [] brackets. For example if
        you would like to look up; project, project_history, and document, then you would use ['project','project_history','document']
    :param min_permission_level: tells us what is the minimum level the user has to be, if they do not meet this requirement
        then the system will formward them onto the permission denied page. Default is 1 (read only)
    :return:
    """

    #Make sure the permission_field is an array/list
    if not isinstance(permission_field, list):
        permission_field = [permission_field]

    #Default NO PERMISSION
    user_permission_level = {}

    #Look into the SQL for that particular field and return it.
    if request.user.is_superuser == True:
        #Add 4 to all permissions
        for row in permission_field:
            user_permission_level[row] = 4
        #Add new_item and administration as 4
        user_permission_level['new_item'] = 4
        user_permission_level['administration'] = 4
        return user_permission_level

    """
    TEMP CODE
    ~~~~~~~~~
    field='project_id'
    results = project.objects.filter(is_deleted="FALSE").values(field).aggregate(Max(field))
    results[field + "__max"]
    """
    for row in permission_field:
        if group_list == None:
            #There is no group. Select the max value :)
            user_groups_results = user_group.objects.filter(
                is_deleted="FALSE",
                username=request.user,
                permission_set__is_deleted="FALSE",
            ).aggregate(Max('permission_set__' + row))
            user_permission_level[row] = user_groups_results['permission_set__' + row + '__max']
        else:
            #There is a group, lets find all permissions connected with this group :) and return the max :)
            group_permission = 0
            for group_id in group_list:
                group_instance = group.objects.get(group_id=group_id['groups_id_id'])

                #Grab user's permission for that group
                user_groups_results = user_group.objects.filter(
                    is_deleted="FALSE",
                    username=request.user,
                    permission_set__is_deleted="FALSE",
                    groups_id=group_instance,
                ).aggregate(Max('permission_set__' + row))

                #Get the max value for the permission
                if group_permission < user_groups_results['permission_set__' + row + '__max']:
                    group_permission = user_groups_results['permission_set__' + row + '__max']

            user_permission_level[row] = group_permission


    """
    The following code is for the menu. We will need to find out if a user can actually ADD any items and do any
    administration.
    """
    permission_results = user_group.objects.filter(
        is_deleted="FALSE",
        username=request.user,
        permission_set__is_deleted="FALSE",
    ).aggregate(
        Max('permission_set__project'),
        Max('permission_set__task'),
        Max('permission_set__requirement'),
        Max('permission_set__organisation'),
        Max('permission_set__customer'),
        Max('permission_set__administration_assign_users_to_groups'),
        Max('permission_set__administration_create_groups'),
        Max('permission_set__administration_create_permission_sets'),
        Max('permission_set__administration_create_users'),
    )

    user_permission_level['new_item'] = max(
        permission_results['permission_set__project__max'],
        permission_results['permission_set__task__max'],
        permission_results['permission_set__requirement__max'],
        permission_results['permission_set__organisation__max'],
        permission_results['permission_set__customer__max'],
    )
    user_permission_level['administration'] = max(
        permission_results['permission_set__administration_assign_users_to_groups__max'],
        permission_results['permission_set__administration_create_groups__max'],
        permission_results['permission_set__administration_create_permission_sets__max'],
        permission_results['permission_set__administration_create_users__max'],
    )
    #END TEMP CODE

    return user_permission_level