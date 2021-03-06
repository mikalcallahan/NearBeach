#Import NearBeach Modules
from .forms import *
from .models import *
from .private_media import *

#Import django Modules
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core import serializers
from django.core.files.storage import FileSystemStorage
from django.db.models import Sum, Q, Min, Value
from django.db.models.functions import Concat
from django.http import HttpResponse,HttpResponseForbidden, HttpResponseRedirect, Http404, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, render_to_response
from django.template import RequestContext, loader
from django.urls import reverse
from .misc_functions import *
from .user_permissions import return_user_permission_level
from datetime import timedelta
from django.db.models import Max
from django.core.mail import EmailMessage, EmailMultiAlternatives
from geolocation.main import GoogleMaps
from django.http import JsonResponse
#from weasyprint import HTML
from urllib.request import urlopen
from weasyprint import HTML
from django.core.mail import send_mail
from urllib.parse import urlparse, urlencode, quote_plus

#import python modules
import datetime, json, simplejson, urllib.parse


@login_required(login_url='login')
def add_campus_to_customer(request, customer_id, campus_id):
    if request.method == "POST":
        # Get the SQL Instances
        customer_instance = customer.objects.get(customer_id=customer_id)
        campus_instances = campus.objects.get(
            campus_id=campus_id,
        )

        # Save the new campus
        submit_campus = customer_campus(
            customer_id=customer_instance,
            campus_id=campus_instances,
            customer_phone='',
            customer_fax='',
            change_user=request.user,
        )
        submit_campus.save()

        response_data = {}
        response_data['customer_campus_id'] = submit_campus.customer_campus_id

        # Go to the form.
        return JsonResponse({'customer_campus_id': submit_campus.customer_campus_id})
    else:
        return HttpResponseBadRequest("Sorry, you can only do this in post.")


@login_required(login_url='login')
def alerts(request):
    compare_time = datetime.datetime.now() + datetime.timedelta(hours=24)

    project_results = project.objects.filter(
        is_deleted="FALSE",
        project_id__in=assigned_user.objects.filter(
            is_deleted="FALSE",
            project_id__isnull=False,
            user_id=request.user,
        ).values('project_id'),
        project_end_date__lte=compare_time,
        project_status__in={'New','Open'},
    )

    task_results = task.objects.filter(
        is_deleted="FALSE",
        task_id__in=assigned_user.objects.filter(
            is_deleted="FALSE",
            task_id__isnull=False,
            user_id=request.user,
        ).values('task_id'),
        task_end_date__lte=compare_time,
        task_status__in={'New','Open'},
    )

    opportunity_results = opportunity.objects.filter(
        is_deleted="FALSE",
        opportunity_id__in=opportunity_permission.objects.filter(
            is_deleted="FALSE",
            assigned_user=request.user,
        ).values('opportunity_id'),
        opportunity_expected_close_date__lte=compare_time,
        opportunity_stage_id__in=list_of_opportunity_stage.objects.filter(
            opportunity_closed="FALSE",
        ).values('opportunity_stage_id'),
    )

    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        quote_stage_id__in=list_of_quote_stage.objects.filter(
            quote_closed="FALSE",
        ).values('quote_stage_id'),
        quote_valid_till__lte=compare_time,
    )

    if not project_results and not task_results and not opportunity_results and not quote_results:
        #There are no alerts, just redirect to dashboard
        return HttpResponseRedirect(reverse('dashboard'))


    # Load the template
    t = loader.get_template('NearBeach/alerts.html')

    # context
    c = {
        'project_results': project_results,
        'task_results': task_results,
        'opportunity_results': opportunity_results,
        'quote_results': quote_results,
    }

    return HttpResponse(t.render(c, request))

@login_required(login_url='login')
def assign_customer_project_task(request, customer_id):
    # Get username_id from User
    current_user = request.user

    if request.POST:

        assign_projects = request.POST.getlist('project_checkbox')
        assign_task = request.POST.getlist('task_checkbox')

        # Instance
        customer_instance = customer.objects.get(customer_id=customer_id)

        """
		We will now assign these projects and task in bulk to the customer
		"""
        print("Assigning customer projects")
        for row in assign_projects:
            project_instance = project.objects.get(project_id=row)
            print("Assigning project: " + project_instance.project_name + " for customer: " + customer_instance.customer_first_name)

            # Project customer
            project_customer_submit = project_customer(
                project_id=project_instance,
                customer_id=customer_instance,
                change_user=request.user,
                # Customer description will have to be programmed in at a later date
            )
            if not project_customer_submit.save():
                print("Error saving")


        print("Assigning customer task")
        for row in assign_task:
            task_instance = task.objects.get(task_id=row)
            print("Assigning task: " + task_instance.task_short_description + " for customer: " + customer_instance.customer_first_name)

            assign_save = task_customer(
                task_id=task_instance,
                customer_id=customer_instance,
                change_user=request.user,
            )
            assign_save.save()

        # Now return to the customer's information
        return HttpResponseRedirect(reverse('customer_information', args={customer_id}))

    # Get Data
    customer_results = customer.objects.get(customer_id=customer_id)

    # Setup connection to the database and query it
    cursor = connection.cursor()

    cursor.execute("""
		SELECT DISTINCT
		  project.*
		FROM
		  user_group
		, project_group
		, project
		WHERE 1=1
		-- USER_GROUPS CONDITIONS
		AND user_group.username_id = %s -- INSERT FILTER HERE!
		-- JOINS --
		AND user_group.group_id = project_group.group_id_id
		AND project_group.project_id_id = project.project_id
		-- END JOINS --	
	""", [current_user.id])
    project_results = namedtuplefetchall(cursor)

    cursor.execute("""
		SELECT DISTINCT
		task.*
		FROM
		user_group
		, task_group
		, task
		WHERE 1=1
		-- USER_GROUPS CONDITIONS
		AND user_group.username_id = %s
		-- JOINS --
		AND user_group.group_id = task_group.group_id_id
		AND task_group.task_id_id=task.task_id
		-- END JOINS --
	""", [current_user.id])
    task_results = namedtuplefetchall(cursor)

    # Load the template
    t = loader.get_template('NearBeach/assign_customer_project_task.html')

    # context
    c = {
        'project_results': project_results,
        'task_results': task_results,
        'customer_results': customer_results,
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def assigned_group_add(request, location_id, destination, group_id=None):
    if request.method == "POST":
        if destination == "project":
            project_groups_submit = project_group(
                project_id=project.objects.get(project_id=location_id),
                group_id=group.objects.get(group_id=group_id),
                change_user=request.user,
            )
            project_groups_submit.save()
        elif destination == "task":
            task_groups_submit = task_group(
                task_id=task.objects.get(task_id=location_id),
                group_id=group.objects.get(group_id=group_id),
                change_user=request.user,
            )
            task_groups_submit.save()


    if destination == "project":
        groups_add_results = group.objects.filter(
            is_deleted="FALSE"
        ).exclude(
            group_id__in = project_group.objects.filter(
                is_deleted="FALSE",
                project_id=location_id,
            ).values('group_id')
        )
    elif destination == "task":
        groups_add_results = group.objects.filter(
            is_deleted="FALSE",
        ).exclude(
            group_id__in=task_group.objects.filter(
                is_deleted="FALSE",
                task_id=location_id,
            ).values('group_id')
        )

    # Load the template
    t = loader.get_template('NearBeach/assigned_groups/assigned_groups_add.html')

    # context
    c = {
        'groups_add_results': groups_add_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def assigned_group_delete(request, location_id, destination):
    if destination == "project":
        project_groups_save = project_group.objects.get(id = location_id)
        project_groups_save.is_deleted = "TRUE"
        if not project_groups_save.save():
            print("Error saving project")


    elif destination == "task":
        task_groups_save = task_group.objects.get(id = location_id)
        task_groups_save.is_deleted = "TRUE"
        if not task_groups_save.save():
            print("Error saving task")


    # Load the template
    t = loader.get_template('NearBeach/blank.html')

    # context
    c = {
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def assigned_group_list(request, location_id, destination):
    if destination == "project":
        group_list_results = project_group.objects.filter(
            is_deleted="FALSE",
            project_id = location_id
        )
    elif destination=="task":
        group_list_results = task_group.objects.filter(
            is_deleted="FALSE",
            task_id=location_id,
        )

    # Load the template
    t = loader.get_template('NearBeach/assigned_groups/assigned_groups_list.html')

    # context
    c = {
        'group_list_results': group_list_results,
        'destination': destination
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def assigned_user_add(request, location_id, destination):
    """
    Assigned user add is a POST function where it will ADD a user to a project/task/opportunity/requirement.
    :param request:
    :param location_id:
    :param destination:
    :return:
    """
    # Load the template
    t = loader.get_template('NearBeach/blank.html')

    # context
    c = {
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def associate(request, project_id, task_id, project_or_task):
    # Submit the data
    submit_result = project_task(
        project_id_id=project_id,
        task_id_id=task_id,
        change_user=request.user,
    )
    submit_result.save()

    # Once we assign them together, we go back to the original
    if project_or_task == "P":
        return HttpResponseRedirect(reverse('project_information', args={project_id}))
    else:
        return HttpResponseRedirect(reverse('task_information', args={task_id}))



@login_required(login_url='login')
def associated_projects(request, task_id):
    """
	We want the ability for the user to assign any project to the current
	task that their group owns. The user will have the ability to
	check to see if they want only new or open, or if they would like
	to see closed task too.
	"""
    task_groups_results = task_group.objects.filter(
        is_deleted="FALSE",
        task_id=task_id,
    ).values('group_id_id')

    permission_results = return_user_permission_level(request, task_groups_results, ['task'])

    if permission_results['task'] == 0:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))


    search_projects = search_project_form()

    # POST
    if request.method == "POST":
        # TO DO! EXTRACT POST AND FILTER RESULTS!!!
        projects_results = project.objects.filter()
    else:
        projects_results = project.objects.filter()

    # Load the template
    t = loader.get_template('NearBeach/associated_project.html')

    # context
    c = {
        'projects_results': projects_results,
        'search_projects': search_projects,
        'task_id': task_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def associated_task(request, project_id):
    """
	We want the ability for the user to assign any task to the current
	project that their group owns. The user will have the ability to
	check to see if they want only new or open, or if they would like
	to see closed task too.
	"""
    project_groups_results = project_group.objects.filter(
        is_deleted="FALSE",
        project_id=project.objects.get(project_id=project_id),
    ).values('group_id_id')


    permission_results = return_user_permission_level(request, project_groups_results,['project'])

    if permission_results['project'] == 0:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))



    search_task = search_task_form()

    # POST
    if request.method == "POST":
        # TO DO! EXTRACT POST AND FILTER RESULTS!!!
        task_results = task.objects.filter()
    else:
        task_results = task.objects.filter()

    # Load the template
    t = loader.get_template('NearBeach/associated_task.html')

    # context
    c = {
        'task_results': task_results,
        'search_task': search_task,
        'project_id': project_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def bug_add(request,location_id, destination,bug_id, bug_client_id):
    #add permissions

    if request.method == "POST":
        """
        Method
        ~~~~~~
        1.) Bring in all the data we need via the URL :)
        2.) Extract the bug_client information - we will use this to contact the bug client server
        3.) Extract an up to date bug information. This is done here (even though it is slow), because at a 
            later date, we might require to gather more information about this bug. This will help.
        4.) Write the information collected VIA the JSON into the database :)
        5.) Notify the end user that this has occurred. This might be by changing the text from "ADD" to "ADDING..." to "ADDED :)"
        """

        #Get the bug client instance - we need to reload this
        bug_client_instance = bug_client.objects.get(
            bug_client_id=bug_client_id,
        )

        #https://bugzilla.nearbeach.org/rest/bug?id=12 example of bugzilla rest platform
        #Most of this will be stored in the database, so we can implement more bug clients simply. :) YAY
        url = bug_client_instance.bug_client_url + bug_client_instance.list_of_bug_client.bug_client_api_url + \
                'bug?id=' + bug_id # This will be implemented into the database as a field
        print(url)

        response = urlopen(url)
        json_data = json.load(response)

        #Save the bug
        bug_submit = bug(
            bug_client=bug_client_instance,
            bug_code=bug_id, #I could not have bug_id twice, so the bug's id becomes bug_code
            bug_description=str(json_data['bugs'][0]['summary']),
            bug_status=str(json_data['bugs'][0]['status']),
            change_user=request.user,
        )
        if destination=="project":
            bug_submit.project=project.objects.get(project_id=location_id)
        elif destination=="task":
            bug_submit.task = task.objects.get(task_id=location_id)
        else:
            bug_submit.requirement=requirement.objects.get(requirement_id=location_id)

        #Save the bug
        bug_submit.save()

        # Load the template
        t = loader.get_template('NearBeach/blank.html')

        # context
        c = {}

        return HttpResponse(t.render(c, request))

    else:
        return HttpResponseBadRequest("Only POST requests allowed")


@login_required(login_url='login')
def bug_client_delete(request, bug_client_id):
    permission_results = return_user_permission_level(request, None, 'bug_client')

    if request.method == "POST" and permission_results['bug_client'] == 4:
        bug_client_update = bug_client.objects.get(bug_client_id=bug_client_id)
        bug_client_update.is_deleted = "TRUE"
        bug_client_update.save()

        # Load the template
        t = loader.get_template('NearBeach/blank.html')

        # context
        c = {}

        return HttpResponse(t.render(c, request))

    else:
        return HttpResponseBadRequest("Only POST requests allowed")



@login_required(login_url='login')
def bug_client_information(request, bug_client_id):
    permission_results = return_user_permission_level(request, None, 'bug_client')

    if permission_results['bug_client'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))
    form_errors = ''
    if request.method == "POST":
        form = bug_client_form(request.POST)
        if form.is_valid():
            #Get required data
            bug_client_name = form.cleaned_data['bug_client_name']
            list_of_bug_client = form.cleaned_data['list_of_bug_client']
            bug_client_url = form.cleaned_data['bug_client_url']

            #Test the link first before doing ANYTHING!
            try:
                url = bug_client_url + list_of_bug_client.bug_client_api_url + 'version'
                print(url)
                response = urlopen(url)
                print("Response gotten")
                data = json.load(response)
                print("Got the JSON")

                bug_client_save = bug_client.objects.get(bug_client_id=bug_client_id)
                bug_client_save.bug_client_name = bug_client_name
                bug_client_save.list_of_bug_client = list_of_bug_client
                bug_client_save.bug_client_url = bug_client_url
                bug_client_save.change_user=request.user

                bug_client_save.save()
                return HttpResponseRedirect(reverse('bug_client_list'))
            except:
                form_errors = "Could not connect to the API"
                print("There was an error")


        else:
            print(form.errors)
            form_errors(form.errors)



    #Get Data
    bug_client_results = bug_client.objects.get(bug_client_id=bug_client_id)
    bug_client_initial = {
        'bug_client_name': bug_client_results.bug_client_name,
        'list_of_bug_client': bug_client_results.list_of_bug_client,
        'bug_client_url': bug_client_results.bug_client_url,
    }

    t = loader.get_template('NearBeach/bug_client_information.html')

    # context
    c = {
        'bug_client_form': bug_client_form(initial=bug_client_initial),
        'bug_client_id': bug_client_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def bug_client_list(request):
    permission_results = return_user_permission_level(request, None, 'bug_client')
    if permission_results['bug_client'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    #Get Data
    bug_client_results = bug_client.objects.filter(
        is_deleted='FALSE',
    )

    # Load the template
    t = loader.get_template('NearBeach/bug_client_list.html')

    # context
    c = {
        'bug_client_results': bug_client_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'bug_client_permission': permission_results['bug_client'],
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def bug_list(request, location_id=None, destination=None):
    #Add permissions later
    if destination == "project":
        bug_results = bug.objects.filter(
            is_deleted="FALSE",
            project=location_id,
        )
    elif destination == "task":
        bug_results = bug.objects.filter(
            is_deleted="FALSE",
            task=location_id,
        )
    elif destination == "requirement":
        bug_results = bug.objects.filter(
            is_deleted="FALSE",
            requirement=location_id,
        )
    else:
        bug_results = bug.objects.filter(
            is_deleted="FALSE",
        )

    # Load the template
    if destination == None:
        t = loader.get_template('NearBeach/bug_list.html')
    else:
        t = loader.get_template('NearBeach/bug_list_specific.html')

    # context
    c = {
        'bug_results': bug_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def bug_search(request, location_id=None, destination=None):
    #Do permissions later
    bug_results = None
    bug_client_id = None
    if request.method == "POST":
        form = bug_search_form(request.POST)
        if form.is_valid():
            #Get the bug client instance
            bug_client_instance = bug_client.objects.get(bug_client_id=form.data['list_of_bug_client'])
            bug_client_id = bug_client_instance.bug_client_id
            print(bug_client_instance)
            print(bug_client_id)

            #Get bugs ids that we want to remove
            if destination == "project":
                existing_bugs = bug.objects.filter(
                    is_deleted="FALSE",
                    project=location_id,
                    bug_client_id=bug_client_id,
                )
            elif destination == "task":
                existing_bugs = bug.objects.filter(
                    is_deleted="FALSE",
                    task=location_id,
                    bug_client_id=bug_client_id,
                )
            else:
                existing_bugs = bug.objects.filter(
                    is_deleted="FALSE",
                    requirement=location_id,
                    bug_client_id=bug_client_id,
                )
            #The values in the URL
            f_bugs = ''
            o_notequals = ''
            v_values =''

            #The for loop
            for idx, row in enumerate(existing_bugs):
                nidx = str(idx+1)
                f_bugs = f_bugs + "&f" + nidx + "=bug_id"
                o_notequals = o_notequals + "&o" + nidx + "=notequals"
                v_values = v_values + "&v" + nidx + "=" + str(row.bug_code)

            exclude_url = f_bugs + o_notequals + v_values


            url = bug_client_instance.bug_client_url \
                  + bug_client_instance.list_of_bug_client.bug_client_api_url \
                  + bug_client_instance.list_of_bug_client.api_search_bugs + form.cleaned_data['search'] \
                  + exclude_url

            print(url)
            response = urlopen(url)
            json_data = json.load(response)
            bug_results = json_data['bugs'] #This could change depending on the API

        else:
            print(form.errors)

    # Load the template
    t = loader.get_template('NearBeach/bug_search.html')

    # context
    c = {
        'bug_search_form': bug_search_form(request.POST or None),
        'bug_results': bug_results,
        'location_id': location_id,
        'destination': destination,
        'bug_client_id': bug_client_id,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def campus_information(request, campus_information):
    permission_results = return_user_permission_level(request, None, 'organisation_campus')

    if permission_results['organisation_campus'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    # Obtain data (before POST if statement as it is used insude)
    campus_results = campus.objects.get(pk=campus_information)

    if campus_results.campus_longitude == None:
        update_coordinates(campus_information)


    # If instance is in POST
    if request.method == "POST":
        # Other save button must have been pressed
        form = campus_information_form(request.POST)
        if form.is_valid():
            # SQL instance
            campus_region_instance = list_of_country_region.objects.get(
                region_id=int(request.POST.get('campus_region_id')))
            campus_country_instance = list_of_country.objects.get(country_id=request.POST.get('campus_country_id'))

            # Save all the data
            campus_results.campus_nickname = form.cleaned_data['campus_nickname']
            campus_results.campus_phone = form.cleaned_data['campus_phone']
            campus_results.campus_fax = form.cleaned_data['campus_fax']
            campus_results.campus_address1 = form.cleaned_data['campus_address1']
            campus_results.campus_address2 = form.cleaned_data['campus_address2']
            campus_results.campus_address3 = form.cleaned_data['campus_address3']
            campus_results.campus_suburb = form.cleaned_data['campus_suburb']
            campus_results.campus_region_id = campus_region_instance
            campus_results.campus_country_id = campus_country_instance
            campus_results.change_user=request.user

            campus_results.save()

            #Update co-ordinates
            update_coordinates(campus_information)

        if 'add_customer_submit' in request.POST:
            # Obtain the ID of the customer
            customer_results = int(request.POST.get("add_customer_select"))

            # Get the SQL Instances
            customer_instance = customer.objects.get(customer_id=customer_results)
            campus_instances = campus.objects.get(organisations_campus_id=campus_information)


            # Save the new campus
            submit_campus = customer_campus(
                customer_id=customer_instance,
                campus_id=campus_instances,
                customer_phone='',
                customer_fax='',
                change_user=request.user,
            )
            submit_campus.save()

            # Go to the form.
            return HttpResponseRedirect(reverse('customer_campus_information', args={submit_campus.customer_campus_id,'CAMP'}))


    # Get Data
    customer_campus_results = customer_campus.objects.filter(
        campus_id=campus_information,
        is_deleted='FALSE',
    )
    add_customer_results = customer.objects.filter(organisation_id=campus_results.organisation_id)
    countries_regions_results = list_of_country_region.objects.all()
    countries_results = list_of_country.objects.all()

    #Get one of the MAP keys
    MAPBOX_API_TOKEN = ''
    GOOGLE_MAP_API_TOKEN = ''

    if hasattr(settings, 'MAPBOX_API_TOKEN'):
        MAPBOX_API_TOKEN = settings.MAPBOX_API_TOKEN
        print("Got mapbox API token: " + MAPBOX_API_TOKEN)
    elif hasattr(settings, 'GOOGLE_MAP_API_TOKEN'):
        GOOGLE_MAP_API_TOKEN = settings.GOOGLE_MAP_API_TOKEN
        print("Got Google Maps API token: " + GOOGLE_MAP_API_TOKEN)


        # Load the template
    t = loader.get_template('NearBeach/campus_information.html')

    # context
    c = {
        'campus_results': campus_results,
        'campus_information_form': campus_information_form(instance=campus_results),
        'customer_campus_results': customer_campus_results,
        'add_customer_results': add_customer_results,
        'countries_regions_results': countries_regions_results,
        'countries_results': countries_results,
        'permission': permission_results['organisation_campus'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'MAPBOX_API_TOKEN': MAPBOX_API_TOKEN,
        'GOOGLE_MAP_API_TOKEN': GOOGLE_MAP_API_TOKEN,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def customer_campus_information(request, customer_campus_id, customer_or_org):
    permission_results = return_user_permission_level(request, None, 'organisation_campus')

    if permission_results['organisation_campus'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    # IF method is post
    if request.method == "POST" and permission_results['organisation_campus'] > 1:
        form = customer_campus_form(request.POST)
        if form.is_valid():
            # Save the data
            save_data = customer_campus.objects.get(customer_campus_id=customer_campus_id)

            save_data.customer_phone = form.cleaned_data['customer_phone']
            save_data.customer_fax = form.cleaned_data['customer_fax']
            save_data.change_user=request.user

            save_data.save()

            """
			Now direct the user back to where they were from. The default
			will be the customer information
			"""
            if customer_or_org == "CAMP":
                return HttpResponseRedirect(reverse('campus_information', args={save_data.campus_id.organisations_campus_id}))
            else:
                return HttpResponseRedirect(reverse('customer_information', args={save_data.customer_id.customer_id}))

    # Get Data
    customer_campus_results = customer_campus.objects.get(customer_campus_id=customer_campus_id)
    campus_results = campus.objects.get(pk=customer_campus_results.campus_id.campus_id)


    # Setup the initial results
    initial = {
        'customer_phone': customer_campus_results.customer_phone,
        'customer_fax': customer_campus_results.customer_fax,
    }

    #Get the mapbox key
    if hasattr(settings, 'MAPBOX_API_TOKEN'):
        MAPBOX_API_TOKEN = settings.MAPBOX_API_TOKEN
        print("Got mapbox API token: " + MAPBOX_API_TOKEN)
    else:
        MAPBOX_API_TOKEN = ''

    #Get one of the MAP keys
    MAPBOX_API_TOKEN = ''
    GOOGLE_MAP_API_TOKEN = ''

    if hasattr(settings, 'MAPBOX_API_TOKEN'):
        MAPBOX_API_TOKEN = settings.MAPBOX_API_TOKEN
        print("Got mapbox API token: " + MAPBOX_API_TOKEN)
    elif hasattr(settings, 'GOOGLE_MAP_API_TOKEN'):
        GOOGLE_MAP_API_TOKEN = settings.GOOGLE_MAP_API_TOKEN
        print("Got Google Maps API token: " + GOOGLE_MAP_API_TOKEN)

    # Load template
    t = loader.get_template('NearBeach/customer_campus.html')

    # context
    c = {
        'customer_campus_form': customer_campus_form(initial=initial),
        'customer_campus_results': customer_campus_results,
        'customer_campus_id': customer_campus_id,
        'customer_or_org': customer_or_org,
        'permission': permission_results['organisation_campus'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'campus_results': campus_results,
        'MAPBOX_API_TOKEN': MAPBOX_API_TOKEN,
        'GOOGLE_MAP_API_TOKEN': GOOGLE_MAP_API_TOKEN,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def customer_information(request, customer_id):
    permission_results = return_user_permission_level(request, None,['assign_campus_to_customer','customer'])

    if permission_results['customer'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST" and permission_results['customer'] > 1:
        # Save everything!
        form = customer_information_form(request.POST, request.FILES)
        if form.is_valid():
            current_user = request.user
            # Save the data
            save_data = customer.objects.get(customer_id=customer_id)

            save_data.customer_title = form.cleaned_data['customer_title']
            save_data.customer_first_name = form.cleaned_data['customer_first_name']
            save_data.customer_last_name = form.cleaned_data['customer_last_name']
            save_data.customer_email = form.cleaned_data['customer_email']
            save_data.change_user=request.user

            # Check to see if the picture has been updated
            update_profile_picture = request.FILES.get('update_profile_picture')
            if not update_profile_picture == None:
                save_data.customer_profile_picture = update_profile_picture

            save_data.save()
        else:
            print(form.errors)

    # Get the instance
    customer_results = customer.objects.get(customer_id=customer_id)
    add_campus_results = campus.objects.filter(organisation_id=customer_results.organisation_id)
    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        customer_id=customer_id,
    )

    # Setup connection to the database and query it
    project_results = project.objects.filter(
        is_deleted="FALSE",
        project_id__in=project_customer.objects.filter(
            is_deleted="FALSE",
            customer_id=customer_id,
        ).values('project_id')
    )

    task_results = task.objects.filter(
        is_deleted="FALSE",
        task_id__in=task_customer.objects.filter(
            is_deleted="FALSE",
            customer_id=customer_id,
        ).values('task_id')
    )

    # The campus the customer is associated to
    """
    We need to limit the amount of opportunities to those that the user has access to.
    """
    user_groups_results = user_group.objects.filter(username=request.user)

    opportunity_permissions_results = opportunity_permission.objects.filter(
        Q(
            Q(assigned_user=request.user)  # User has permission
            | Q(group_id__in=user_groups_results.values('group_id'))  # User's group have permission
            | Q(all_user='TRUE')  # All users have access
        )
    )
    opportunity_results = opportunity.objects.filter(
        customer_id=customer_id,
        opportunity_id__in=opportunity_permissions_results.values('opportunity_id')
    )
    #For when customer have an organisation
    campus_results = customer_campus.objects.filter(
        customer_id=customer_id,
        is_deleted='FALSE',
    )
    #For when customer do not have an organistion
    customer_campus_results = campus.objects.filter(
        is_deleted="FALSE",
        customer=customer_id,
    )


    try:
        profile_picture = customer_results.customer_profile_picture.url
    except:
        profile_picture = ''

    # Date required to initiate date
    today = datetime.datetime.now()

    """
    We need to do some basic formulations with the hour and and minutes.
    For the hour we need to find all those who are in the PM and
    change both the hour and meridiem accordingly.
    For the minute, we have to create it in 5 minute blocks.
    """
    hour = today.hour
    minute = int(5 * round(today.minute / 5.0))
    meridiems = 'AM'

    if hour > 12:
        hour = hour - 12
        meridiems = 'PM'
    elif hour == 0:
        hour = 12

    # load template
    t = loader.get_template('NearBeach/customer_information.html')

    # context
    c = {
        'customer_information_form': customer_information_form(
            instance=customer_results,
            initial={
                'start_date_year': today.year,
                'start_date_month': today.month,
                'start_date_day': today.day,
                'start_date_hour': hour,
                'start_date_minute': minute,
                'start_date_meridiems': meridiems,
            }),
        'campus_results': campus_results,
        'customer_campus_results': customer_campus_results,
        'add_campus_results': add_campus_results,
        'customer_results': customer_results,
        'media_url': settings.MEDIA_URL,
        'profile_picture': profile_picture,
        'project_results': project_results,
        'task_results': task_results,
        'opportunity_results': opportunity_results,
        'PRIVATE_MEDIA_URL': settings.PRIVATE_MEDIA_URL,
        'customer_id': customer_id,
        'customer_permissions': permission_results['customer'],
        'assign_campus_to_customer_permission': permission_results['assign_campus_to_customer'],
        'quote_results':quote_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard(request):
    permission_results = return_user_permission_level(request, None, 'project')

    # Load the template
    t = loader.get_template('NearBeach/dashboard.html')

    # context
    c = {
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))

@login_required(login_url='login')
def dashboard_active_projects(request):
    #Get Data
    assigned_users_results = assigned_user.objects.filter(
        is_deleted='FALSE',
        user_id=request.user,
        project_id__isnull=False,
    )\
        .exclude(project_id__project_status='Resolved').exclude(project_id__project_status='Closed')\
        .values('project_id__project_id','project_id__project_name','project_id__project_end_date').distinct()


    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/active_projects.html')

    # context
    c = {
        'assigned_users_results': assigned_users_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_active_quotes(request):
    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        quote_stage_id__in=list_of_quote_stage.objects.filter(
            #We do not want to remove any quote with deleted stage
            quote_closed="FALSE"
        ).values('quote_stage_id')
    )

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/active_quotes.html')

    # context
    c = {
        'quote_results': quote_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_active_requirement(request):
    requirement_results = requirement.objects.filter(
        is_deleted="FALSE",
        requirement_status__in=list_of_requirement_status.objects.filter(
            requirement_status_is_closed="FALSE"
            #Do not worry about deleted status. We want them to appear and hopefully the user will
            #update these requirement_status.
        ).values('requirement_status_id')
    )

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/active_requirements.html')


    # context
    c = {
        'requirement_results': requirement_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_active_task(request):
    # Get Data
    assigned_users_results = assigned_user.objects.filter(
        is_deleted='FALSE',
        user_id=request.user,
        task_id__isnull=False,
    )\
        .exclude(task_id__task_status='Resolved')\
        .exclude(task_id__task_status='Completed')\
        .values('task_id__task_id','task_id__task_short_description','task_id__task_end_date').distinct()

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/active_tasks.html')

    # context
    c = {
        'assigned_users_results': assigned_users_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_group_active_projects(request):
    active_projects_results = project.objects.filter(
        is_deleted="FALSE",
        project_id__in=project_group.objects.filter(
            is_deleted="FALSE",
            group_id__in=user_group.objects.filter(
                is_deleted="FALSE",
                username_id=request.user.id
            ).values('group'),
        ).values('project_id'),
    )

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/group_active_projects.html')

    # context
    c = {
        'active_projects_results': active_projects_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_group_active_task(request):
    active_task_results = task.objects.filter(
        is_deleted="FALSE",
        task_id__in=task_group.objects.filter(
            is_deleted="FALSE",
            group_id__in=user_group.objects.filter(
                is_deleted="FALSE",
                username_id=request.user.id
            ).values('group')
        ).values('task_id')
    )
    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/group_active_tasks.html')

    # context
    c = {
        'active_task_results': active_task_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_group_opportunities(request):
    active_group_opportunities = opportunity.objects.filter(
        is_deleted="FALSE",
        opportunity_id__in=opportunity_permission.objects.filter(
            is_deleted="FALSE",
            group_id__in=user_group.objects.filter(
                is_deleted="FALSE",
                username_id=request.user,
            ).values('group_id'),
        ).values('opportunity_id'),
    )

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/group_opportunities.html')

    # context
    c = {
        'active_group_opportunities': active_group_opportunities,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_opportunities(request):
    # Get username_id from User
    current_user = request.user

    # Setup connection to the database and query it
    cursor = connection.cursor()

    cursor.execute("""
        SELECT DISTINCT
        opportunities.opportunity_id
        , opportunities.opportunity_name
        , organisation.organisation_id
        , organisation.organisation_name
        , customer.customer_id
        , customer.customer_first_name
        , customer.customer_last_name
        , list_of_opportunity_stage.opportunity_stage_description
        , opportunities.opportunity_expected_close_date


        FROM 
        opportunity_permission LEFT JOIN user_group
        ON opportunity_permission.assigned_user_id = user_group.username_id
        , opportunities JOIN organisation
        ON opportunities.organisation_id_id = organisation.organisation_id
        LEFT JOIN customer
        ON opportunities.customer_id_id = customer.customer_id
        JOIN list_of_opportunity_stage
        ON opportunities.opportunity_stage_id_id = list_of_opportunity_stage.opportunity_stage_id
        WHERE 1=1
        AND opportunity_permission.opportunity_id_id = opportunities.opportunity_id
        AND list_of_opportunity_stage.opportunity_stage_description NOT LIKE '%%Close%%'
        AND opportunity_permission.assigned_user_id = %s
    """, [current_user.id])
    active_opportunities = namedtuplefetchall(cursor)

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/opportunities.html')

    # context
    c = {
        'active_opportunities': active_opportunities,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def delete_campus_contact(request, customer_campus_id, cust_or_camp):
    """
    So... I will need to add in security to define IF a user can do this action
    """
    save_customer_campus = customer_campus.objects.get(pk=customer_campus_id)
    save_customer_campus.is_deleted = "TRUE"
    save_customer_campus.change_user = request.user
    save_customer_campus.save()

    if cust_or_camp=="CAMP":
        return HttpResponseRedirect(reverse('campus_information', args={save_customer_campus.campus_id.organisations_campus_id}))
    else:
        return HttpResponseRedirect(reverse('customer_information', args={save_customer_campus.customer_id.customer_id}))


@login_required(login_url='login')
def delete_cost(request, cost_id, location_id, project_or_task):
    # Delete the cost
    cost_save = cost.objects.get(pk=cost_id)
    cost_save.is_deleted = "TRUE"
    cost_save.change_user=request.user
    cost_save.save()

    # Once we assign them together, we go back to the original
    if project_or_task == "P":
        return HttpResponseRedirect(reverse('project_information', args={location_id}))
    else:
        return HttpResponseRedirect(reverse('task_information', args={location_id}))


@login_required(login_url='login')
def delete_document(request, document_key):
    # Delete the document
    document = document.objects.get(document_key=document_key)
    document.is_deleted = "TRUE"
    document.change_user=request.user
    document.save()

    document_permission_save = document_permission.objects.get(document_key=document_key)
    document_permission_save.is_deleted = "TRUE"
    document_permission_save.change_user=request.user
    document_permission_save.save()

    print("Deleted Document: " + document_key)

    #Return a blank page for fun
    t = loader.get_template('NearBeach/blank.html')

    # context
    c = {}

    return HttpResponse(t.render(c, request))
    #SoMuchFun


@login_required(login_url='login')
def diagnostic_information(request):
    permission_results = return_user_permission_level(request, None, None)

    # reCAPTCHA
    RECAPTCHA_PUBLIC_KEY = ''
    if hasattr(settings, 'RECAPTCHA_PUBLIC_KEY'):
        RECAPTCHA_PUBLIC_KEY = settings.RECAPTCHA_PUBLIC_KEY

    # Diagnostic Template
    t = loader.get_template('NearBeach/diagnostic_information.html')

    c = {
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'RECAPTCHA_PUBLIC_KEY': RECAPTCHA_PUBLIC_KEY,
        'diagnostic_test_document_upload_form': diagnostic_test_document_upload_form(),
    }

    return HttpResponse(t.render(c,request))



@login_required(login_url='login')
def diagnostic_test_database(request):
    """
    Ping the user's database. If there is an issue then report it
    """
    User.objects.filter(username=request.user)

    t = loader.get_template('NearBeach/blank.html')

    c = {}

    return HttpResponse(t.render(c,request))




@login_required(login_url='login')
def diagnostic_test_document_upload(request):
    """
    Upload user's document and send back a link to the document. Please note the document will be fetched using
    ajax so test for any issues
    """
    print("Sending in test")
    if request.method == "POST":
        print("Request is in post")
        if request.FILES == None:
            print("There was an error with the file")
            return HttpResponseBadRequest('File needs to be uploaded. Refresh the page and try again')

        # Get the file data
        print("Checking the file")
        file = request.FILES['document']

        # Data objects required
        print("Getting the filename string")
        filename = str(file)

        """
        File Uploads
        """
        print("Saving the document")
        document_save = document(
            document_description=filename,
            document=file,
            change_user=request.user,
        )
        document_save.save()

        print("Saving document permissions")
        document_permissions_save = document_permission(
            document_key=document_save,
            change_user=request.user,
        )
        document_permissions_save.save()

        #Time to send back the link to the user
        t = loader.get_template('NearBeach/diagnostic/test_document_download.html')

        c = {
            'document_key': document_save.document_key,
        }

        return HttpResponse(t.render(c,request))

    return HttpResponseBadRequest("Something went wrong")


@login_required(login_url='login')
def diagnostic_test_email(request):
    """
    Method
    ~~~~~~
    1.) Gather the required variables
    2.) Send an email to noreply@nearbeach.org
    3.) If the email fails at ANY point, send back an error
    4.) If the email works, send back a blank page
    """
    try:
        #Check variables
        EMAIL_HOST_USER = settings.EMAIL_HOST_USER
        EMAIL_BACKEND = settings.EMAIL_BACKEND
        EMAIL_USE_TLS = settings.EMAIL_USE_TLS
        EMAIL_HOST = settings.EMAIL_HOST
        EMAIL_PORT = settings.EMAIL_PORT
        EMAIL_HOST_USER = settings.EMAIL_HOST_USER
        EMAIL_HOST_PASSWORD = settings.EMAIL_HOST_PASSWORD

    except:
        #It failed. Send back an error
        return HttpResponseBadRequest("Variables have not been fully setup in settings.py")

    try:
        email = EmailMultiAlternatives(
            'NearBeach Diagnostic Test',
            'Ignore email - diagnostic test',
            settings.EMAIL_HOST_USER,
            ['donotreply@nearbeach.org'],
        )
        if not email.send():
            return HttpResponseBadRequest("Email did not send correctly.")
    except:
        return HttpResponseBadRequest("Email failed")

    # Diagnostic Template
    t = loader.get_template('NearBeach/blank.html')

    c = {
    }

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def diagnostic_test_location_services(request):
    """
    Method
    ~~~~~~
    1.) Check to make sure MAPBOX keys are inplace
    2.) If exists, test keys
    3.) If pass, returns pass. If fails, return fail

    4.) Check to make sure GOOGLE keys are inplace
    5.) If exists, test keys
    6.) If pass, returns pass. If fails, return fail

    7.) No keys, return error
    """

    try:
        MAPBOX_API_TOKEN = settings.MAPBOX_API_TOKEN

        try:
            address_coded = urllib.parse.quote_plus("Flinders Street Melbourne")
            print(address_coded)

            url = "https://api.mapbox.com/geocoding/v5/mapbox.places/" + address_coded + ".json?access_token=" + settings.MAPBOX_API_TOKEN
            # response = urllib.urlopen(url)
            response = urllib.request.urlopen(url)
            data = json.loads(response.read())

            longatude = data["features"][0]["center"][0]
            latitude = data["features"][0]["center"][1]
            #It worked - now it will just leave
        except:
            return HttpResponseBadRequest("Sorry, could not contact Mapbox")
    except:
        try:
            google_maps = GoogleMaps(api_key=settings.GOOGLE_MAP_API_TOKEN)
            location = google_maps.search(location="Flinders Street Melbourne")
            first_location = location.first()

            #Save the data
            ongitude = first_location.lng
            latitude = first_location.lat
        except:
            return HttpResponseBadRequest("Could not contact Google Server")

    t = loader.get_template('NearBeach/blank.html')

    c = {}

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def diagnostic_test_recaptcha(request):
    if request.method == "POST":
        """
        Method
        ~~~~~~
        1.) Check to make sure reCAPTCHA keys are inplace
        2.) If exists, test keys
        3.) If pass, returns pass. If fails, return fail
    
        4.) No keys, return error
        """
        # reCAPTCHA
        RECAPTCHA_PUBLIC_KEY = ''
        RECAPTCHA_PRIVATE_KEY = ''
        if hasattr(settings, 'RECAPTCHA_PUBLIC_KEY') and hasattr(settings, 'RECAPTCHA_PRIVATE_KEY'):
            RECAPTCHA_PUBLIC_KEY = settings.RECAPTCHA_PUBLIC_KEY
            RECAPTCHA_PRIVATE_KEY = settings.RECAPTCHA_PRIVATE_KEY
        else:
            #Getting data from settings file has failed.
            return HttpResponseBadRequest("Either RECAPTCHA_PUBLIC_KEY or RECAPTCHA_PRIVATE_KEY has not been correctly setup in your settings file.")

        """
        As the Google documentation states. I have to send the request back to
        the given URL. It gives back a JSON object, which will contain the
        success results.
    
        Method
        ~~~~~~
        1.) Collect the variables
        2.) With the data - encode the variables into URL format
        3.) Send the request to the given URL
        4.) The response will open and store the response from GOOGLE
        5.) The results will contain the JSON Object
        """
        recaptcha_response = request.POST.get('g-recaptcha-response')
        print("RECAPTCHA RESPONSE:" + str(recaptcha_response))
        url = 'https://www.google.com/recaptcha/api/siteverify'
        values = {
            'secret': RECAPTCHA_PRIVATE_KEY,
            'response': recaptcha_response
        }
        response = urlopen(url, urllib.parse.urlencode(values).encode('utf8'))
        result = json.load(response)

        print(result)

        # Check to see if the user is a robot. Success = human
        if not result['success']:
            return HttpResponseBadRequest("Failed recaptcha!\n" + str(result))

    t = loader.get_template('NearBeach/blank.html')

    c = {}

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def email(request,location_id,destination):
    permission_results = return_user_permission_level(request, None, 'email')

    if permission_results['email'] < 2:
        return HttpResponseRedirect(reverse('permission_denied'))

    """
    organisation
    customer
    project
    task
    opportunity
    quote
    """
    if request.method == "POST":
        form = email_form(
            request.POST,
            location_id=location_id,
            destination=destination,
        )
        if form.is_valid():
            #Extract form data
            organisation_email = form.cleaned_data['organisation_email']
            email_quote = form.cleaned_data['email_quote']

            to_email = []
            cc_email = []
            bcc_email = []
            from_email = ''

            #Get the current user's email
            current_user = User.objects.get(id=request.user.id)

            if current_user.email == '':
                from_email = settings.EMAIL_HOST_USER
            else:
                from_email = current_user.email

            if organisation_email:
                to_email.append(organisation_email)

            for row in form.cleaned_data['to_email']:
                to_email.append(row.customer_email)

            for row in form.cleaned_data['cc_email']:
                cc_email.append(row.customer_email)

            for row in form.cleaned_data['bcc_email']:
                bcc_email.append(row.customer_email)

            email = EmailMultiAlternatives(
                form.cleaned_data['email_subject'],
                form.cleaned_data['email_content'],
                from_email,
                to_email,
                bcc_email,
                cc=cc_email,
                reply_to=['nearbeach@tpg.com.au'],
            )
            email.attach_alternative(form.cleaned_data['email_content'],"text/html")

            """
            If this is a quote and the email_quote is ticked, then we send the quote information
            """
            if email_quote == True:
                """
                Method
                ~~~~~~
                1.) Get quote instance to extract UUID
                2.) Get the template ID from form
                3.) Use the above information to get the PDF
                4.) Attach PDF
                """
                quote_results = quote.objects.get(quote_id=location_id)
                quote_template_id = request.POST.get('quote_template_description')
                print("Quote Template ID: " + str(quote_template_id))

                #Generating PDF
                url_path = "http://" + request.get_host() + "/preview_quote/" + str(quote_results.quote_uuid) + "/" + str(quote_template_id) + "/"
                print("URL LOCATION:")
                print(url_path)
                html = HTML(url_path)
                pdf_results = html.write_pdf()

                #Attach the PDF
                email.attach("Quote - " + str(quote_results.quote_id), pdf_results, 'application/pdf')


            email.send(fail_silently=False)



            """
            Once the email has been sent with no errors. Then we save the content. :)
            First create the content email
            Then apply who got sent the email.
            """
            print(email_content)
            email_content_submit=email_content(
                email_subject= form.cleaned_data['email_subject'],
                email_content=form.cleaned_data['email_content'],
                change_user=request.user,
                is_private=form.cleaned_data['is_private'],
            )
            email_content_submit.save()

            for row in form.cleaned_data['to_email']:
                email_contact_submit=email_contact(
                    email_content=email_content_submit,
                    to_customer=customer.objects.get(customer_id=row.customer_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()

            for row in form.cleaned_data['cc_email']:
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    cc_customer=customer.objects.get(customer_id=row.customer_id),
                    change_user = request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()

            for row in form.cleaned_data['bcc_email']:
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    bcc_customer=customer.objects.get(customer_id=row.customer_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()

            if destination == "organisation":
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    organisations=organisation.objects.get(organisation_id=location_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()
            elif destination == "project":
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    project=project.objects.get(project_id=location_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()
            elif destination == "task":
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    task=task.objects.get(task_id=location_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()
            elif destination == "opportunity":
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    opportunity=opportunity.objects.get(opportunity_id=location_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()
            elif destination == "quote":
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    quotes=quote.objects.get(quote_id=location_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()







            #Now go back where you came from
            if destination == "organisation":
                return HttpResponseRedirect(reverse('organisation_information', args={location_id}))
            elif destination == "customer":
                return HttpResponseRedirect(reverse('customer_information', args={location_id}))
            elif destination == "project":
                return HttpResponseRedirect(reverse('project_information', args={location_id}))
            elif destination == "task":
                return HttpResponseRedirect(reverse('task_information', args={location_id}))
            elif destination == "opportunity":
                return HttpResponseRedirect(reverse('opportunity_information', args={location_id}))
            elif destination == "quote":
                return HttpResponseRedirect(reverse('quote_information', args={location_id}))
            else:
                return HttpResponseRedirect(reverse('dashboard'))



        else:
            print("ERROR with email form.")
            print(form.errors)

    #Template
    t = loader.get_template('NearBeach/email.html')

    quote_template_results = ''

    #Initiate form
    if destination == "organisation":
        organisation_results = organisation.objects.get(organisation_id=location_id)
        initial = {
            'organisation_email': organisation_results.organisation_email,
        }
    elif destination == "customer":
        customer_results = customer.objects.get(
            is_deleted="FALSE",
            customer_id=location_id
        )
        initial = {
            'to_email': customer_results.customer_id,
        }
    elif destination == "project":
        customer_results = customer.objects.filter(
            customer_id__in=project_customer.objects.filter(
                is_deleted="FALSE",
                project_id=location_id,
            ).values('customer_id')
        )
        print(customer_results)
        initial = {
            'to_email': customer_results,
        }
    elif destination == "task":
        task_results = task.objects.get(task_id=location_id)
        if task_results.organisation_id:
            customer_results = customer.objects.filter(
                is_deleted="FALSE",
                customer_id = task_customer.objects.filter(
                    is_deleted="FALSE",
                    task_id=location_id,
                ).values('customer_id')
            )
        else:
            customer_results = customer.objects.filter(
                customer_id__in=task_customer.objects.filter(
                    is_deleted="FALSE",
                    task_id=location_id,
                ).values('customer_id')
            )
        initial = {
            'to_email': customer_results,
        }
    elif destination == "opportunity":
        customer_results = customer.objects.filter(
            Q(is_deleted="FALSE") &
            Q(
                Q(customer_id__in=opportunity.objects.filter(
                    is_deleted="FALSE",
                    opportunity_id=location_id,
                ).values('customer_id')) |
                Q(customer_id__in=customer.objects.filter(
                    is_deleted="FALSE",
                    organisation_id__in=opportunity.objects.filter(
                        opportunity_id=location_id
                    ).values('organisation_id')
                ).values('customer_id')
                )
            )
        )
        initial = {
            'to_email': customer_results,
        }

    elif destination == "quote":
        quote_template_results = quote_template.objects.filter(
            is_deleted="FALSE",
        )
        customer_results = customer.objects.filter(
            is_deleted="FALSE",
            customer_id__in=quote_responsible_customer.objects.filter(
                is_deleted="FALSE",
                quote_id=location_id,
            ).values('customer_id')
        )
        initial = {
            'to_email': customer_results,
        }
    else:
        print("FUCK! Something went wrong")


    # context
    c = {
        'email_form': email_form(
            initial=initial,
            location_id=location_id,
            destination=destination,
        ),
        'destination': destination,
        'location_id': location_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'quote_template_results': quote_template_results,

    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def email_history(request,location_id,destination):
    permission_results = return_user_permission_level(request, None, 'email')

    #Get data
    if destination == "organisation":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                Q(is_deleted="FALSE") &
                Q(organisation_id=location_id) &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    elif destination == "customer":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                (
                        Q(to_customer=location_id) |
                        Q(cc_customer=location_id)
                ) &
                Q(is_deleted="FALSE") &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    elif destination == "project":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                Q(project=location_id) &
                Q(is_deleted="FALSE") &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    elif destination == "task":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                Q(task_id=location_id) &
                Q(is_deleted="FALSE") &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    elif destination == "opportunity":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                Q(opportunity_id=location_id) &
                Q(is_deleted="FALSE") &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    elif destination == "quote":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                Q(quotes=location_id) &
                Q(is_deleted="FALSE") &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    else:
        email_results = ''

    # Template
    t = loader.get_template('NearBeach/email_history.html')

    print(email_results)

    # context
    c = {
        'destination': destination,
        'location_id': location_id,
        'email_results': email_results,
        'email_permission': permission_results['email'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def email_information(request,email_content_id):
    permission_results = return_user_permission_level(request, None, 'email')

    if permission_results['email'] < 1:
        return HttpResponseRedirect(reverse('permission_denied'))

    email_content_results = email_content.objects.get(
        is_deleted="FALSE",
        email_content_id=email_content_id,
    )

    to_email_results = email_contact.objects.filter(
        is_deleted="FALSE",
        email_content_id=email_content_id,
        to_customer__isnull=False,
    )
    cc_email_results = email_contact.objects.filter(
        is_deleted="FALSE",
        email_content_id=email_content_id,
        cc_customer__isnull=False,
    )
    bcc_email_results = email_contact.objects.filter(
        is_deleted="FALSE",
        email_content_id=email_content_id,
        bcc_customer__isnull=False,
    )

    #Check to make sure it isn't private
    if email_content_results.is_private == True and not email_content_results.change_user == request.user:
        #The email is private and the user is not the original creator
        return HttpResponseRedirect(reverse('permission_denied'))

    initial = {
        'email_subject': email_content_results.email_subject,
        'email_content': email_content_results.email_content,
    }

    # Template
    t = loader.get_template('NearBeach/email_information.html')

    # context
    c = {
        'email_content_results': email_content_results,
        'email_information_form': email_information_form(initial=initial),
        'to_email_results': to_email_results,
        'cc_email_results': cc_email_results,
        'bcc_email_results': bcc_email_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],

    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def extract_quote(request, quote_uuid,quote_template_id):
    #Create the PDF
    url_path = "http://" + request.get_host() + "/preview_quote/" + quote_uuid + "/" + quote_template_id + "/"
    html = HTML(url_path)
    pdf_results = html.write_pdf()

    #Setup the response
    response = HttpResponse(pdf_results,content_type='application/pdf')
    response['Content-Disposition']='attachment; filename="NearBeach Quote.pdf"'

    return response


@login_required(login_url='login')
def index(request):
    """
	The index page determines if a particular user has logged in. It will
	follow the following steps
	
	Method
	~~~~~~
	1.) If there is a user logged in, if not, send them to login
	2.) Find out if this user should be in the system, if not send them to
		invalid view
	3.) If survived this far the user will be sent to "Active Projects"
	"""
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse('login'))
    else:
        return HttpResponseRedirect(reverse('dashboard'))

    # Default
    return HttpResponseRedirect(reverse('login'))



@login_required(login_url='login')
def kanban_edit_card(request,kanban_card_id):
    kanban_card_results = kanban_card.objects.get(kanban_card_id=kanban_card_id)
    if (
        kanban_card_results.project
        or kanban_card_results.task
        or kanban_card_results.requirement
    ):
        linked_card = True
    else:
        linked_card = False


    permission_results = return_user_permission_level(request, None,['kanban','kanban_card','kanban_comment'])

    if permission_results['kanban'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))


    if request.method == "POST" and permission_results['kanban'] > 1:
        form = kanban_card_form(
            request.POST,
            kanban_board_id=kanban_card_results.kanban_board_id,
        )
        if form.is_valid():
            #Get required data
            kanban_card_instance = kanban_card.objects.get(kanban_card_id=kanban_card_id)
            current_user = request.user

            kanban_column_extract=form.cleaned_data['kanban_column']
            kanban_level_extract=form.cleaned_data['kanban_level']

            if linked_card == False:
                kanban_card_instance.kanban_card_text=form.cleaned_data['kanban_card_text']
            kanban_card_instance.kanban_column_id=kanban_column_extract.kanban_column_id
            kanban_card_instance.kanban_level_id =kanban_level_extract.kanban_level_id
            kanban_card_instance.save()

            #Comments section
            kanban_comment_extract = form.cleaned_data['kanban_card_comment']

            if not kanban_comment_extract == '':


                kanban_comment_submit = kanban_comment(
                    kanban_card_id=kanban_card_instance.kanban_card_id ,
                    kanban_comment=kanban_comment_extract,
                    user_id=current_user,
                    user_infomation=current_user.id,
                    change_user=request.user,
                )
                kanban_comment_submit.save()


            #Let's return the CARD back so that the user does not have to refresh
            t = loader.get_template('NearBeach/kanban/kanban_card_information.html')

            c = {
                'kanban_card_submit': kanban_comment_extract,
            }

        else:
            print(form.errors)
            HttpResponseBadRequest(form.errors)

    #Get data

    kanban_comment_results = kanban_comment.objects.filter(kanban_card_id=kanban_card_id)


    # Get template
    t = loader.get_template('NearBeach/kanban/kanban_edit_card.html')

    # context
    c = {
        'kanban_card_form': kanban_card_form(
            kanban_board_id=kanban_card_results.kanban_board_id,
            instance=kanban_card_results,
        ),
        'kanban_permission': permission_results['kanban'],
        'kanban_card_permission': permission_results['kanban_card'],
        'kanban_comment_permission': permission_results['kanban_comment'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'kanban_comment_results': kanban_comment_results,
        'kanban_card_id': kanban_card_id,
        'linked_card': linked_card,
        'kanban_card_results': kanban_card_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def kanban_edit_xy_name(request,location_id, destination):
    """
    This function is for editing both kanban column and level names.
    PERMISSIONS WILL NEED TO BE ADDED!
    """

    if destination == "column":
        kanban_xy_name = kanban_column.objects.get(kanban_column_id=location_id).kanban_column_name.encode('utf8')
    elif destination == "level":
        kanban_xy_name = kanban_level.objects.get(kanban_level_id=location_id).kanban_level_name.decode('utf8')
    else:
        kanban_xy_name = ''

    # load template
    t = loader.get_template('NearBeach/kanban/kanban_edit_xy_name.html')

    # context
    c = {
        'kanban_edit_xy_name_form': kanban_edit_xy_name_form(initial={
            'kanban_xy_name': kanban_xy_name,
        })
    }

    return HttpResponse(t.render(c, request))



def kanban_information(request,kanban_board_id):
    permission_results = return_user_permission_level(request, None,['kanban'])

    if permission_results['kanban'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    #Get the required information
    kanban_board_results = kanban_board.objects.get(kanban_board_id=kanban_board_id)
    kanban_level_results = kanban_level.objects.filter(
        is_deleted="FALSE",
        kanban_board=kanban_board_id,
    ).order_by('kanban_level_sort_number')
    kanban_column_results = kanban_column.objects.filter(
        is_deleted="FALSE",
        kanban_board=kanban_board_id,
    ).order_by('kanban_column_sort_number')
    kanban_card_results = kanban_card.objects.filter(
        is_deleted="FALSE",
        kanban_board=kanban_board_id,
    ).order_by('kanban_card_sort_number')

    t = loader.get_template('NearBeach/kanban_information.html')

    # context
    c = {
        'kanban_board_id': kanban_board_id,
        'kanban_board_results': kanban_board_results,
        'kanban_level_results': kanban_level_results,
        'kanban_column_results': kanban_column_results,
        'kanban_card_results': kanban_card_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


def kanban_move_card(request,kanban_card_id,kanban_column_id,kanban_level_id):
    if request.method == "POST":
        kanban_card_result = kanban_card.objects.get(kanban_card_id=kanban_card_id)
        kanban_card_result.kanban_column_id = kanban_column.objects.get(kanban_column_id=kanban_column_id)
        kanban_card_result.kanban_level_id = kanban_level.objects.get(kanban_level_id=kanban_level_id)
        kanban_card_result.save()

        #Send back blank like a crazy person.
        t = loader.get_template('NearBeach/blank.html')

        # context
        c = {}

        return HttpResponse(t.render(c, request))
    else:
        return HttpResponseBadRequest("This request can only be through POST")


@login_required(login_url='login')
def kanban_list(request):
    permission_results = return_user_permission_level(request, None,['kanban'])

    if permission_results['kanban'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    kanban_board_results = kanban_board.objects.filter(
        is_deleted="FALSE",
    )

    t = loader.get_template('NearBeach/kanban_list.html')

    # context
    c = {
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'kanban_permission': permission_results['kanban'],
        'kanban_board_results': kanban_board_results,
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def kanban_new_card(request,kanban_board_id):
    permission_results = return_user_permission_level(request, None,['kanban'])

    if permission_results['kanban'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        form = kanban_card_form(request.POST,kanban_board_id=kanban_board_id)
        if form.is_valid():
            kanban_column_results=form.cleaned_data['kanban_column']
            kanban_level_results=form.cleaned_data['kanban_level']

            #To add the card at the bottom of the pack, we first need to get the max value
            max_value_results = kanban_card.objects.filter(
                kanban_column=kanban_column_results.kanban_column_id,
                kanban_level=kanban_level_results.kanban_level_id,
            ).aggregate(Max('kanban_card_sort_number'))

            #In case it returns a none
            try:
                max_value = max_value_results['kanban_card_sort_number__max'] + 1
            except:
                max_value = 0

            kanban_card_submit = kanban_card(
                kanban_card_text=form.cleaned_data['kanban_card_text'],
                kanban_column=kanban_column_results,
                kanban_level=kanban_level_results,
                change_user=request.user,
                kanban_card_sort_number=max_value,
                kanban_board_id=kanban_board_id,
            )
            kanban_card_submit.save()

            #Let's return the CARD back so that the user does not have to refresh
            t = loader.get_template('NearBeach/kanban/kanban_card_information.html')

            c = {
                'kanban_card_submit': kanban_card_submit,
            }

            return HttpResponse(t.render(c, request))

        else:
            print(form.errors)


    kanban_column_results = kanban_column.objects.filter(kanban_board=kanban_board_id)
    kanban_level_results = kanban_level.objects.filter(kanban_board=kanban_board_id)

    t = loader.get_template('NearBeach/kanban/kanban_new_card.html')

    # context
    c = {
        'kanban_column_results': kanban_column_results,
        'kanban_level_results': kanban_level_results,
        'kanban_card_form': kanban_card_form(
            kanban_board_id=kanban_board_id,
        ),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'kanban_board_id': kanban_board_id,
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def kanban_new_link(request,kanban_board_id,location_id='',destination=''):
    permission_results = return_user_permission_level(request, None,['kanban'])

    if permission_results['kanban'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        form=kanban_new_link_form(
            request.POST,
            kanban_board_id=kanban_board_id,
        )
        if form.is_valid():
            #Check to make sure we have not connected the item before. If so, send them a band response
            if (
                    (kanban_card.objects.filter(project_id=location_id,is_deleted="FALSE") and destination == "project")
                    or (kanban_card.objects.filter(task_id=location_id,is_deleted="FALSE") and destination == "task")
                    or (kanban_card.objects.filter(requirement_id=location_id,is_deleted="FALSE") and destination == "requirement")
                ):
                #Sorry, this already exists
                return HttpResponseBadRequest("Card already exists") #How do we fix these for AJAX - send back an error message

            #Get form data
            kanban_column = form.cleaned_data['kanban_column']
            kanban_level = form.cleaned_data['kanban_level']

            # To add the card at the bottom of the pack, we first need to get the max value
            max_value_results = kanban_card.objects.filter(
                kanban_column=kanban_column.kanban_column_id,
                kanban_level=kanban_level.kanban_level_id,
            ).aggregate(Max('kanban_card_sort_number'))

            # In case it returns a none
            try:
                max_value = max_value_results['kanban_card_sort_number__max'] + 1
            except:
                max_value = 0

            #Start by creating the card
            kanban_card_submit = kanban_card(
                change_user=request.user,
                kanban_column = kanban_column,
                kanban_level = kanban_level,
                kanban_card_sort_number=max_value,
                kanban_board = kanban_board.objects.get(kanban_board_id=kanban_board_id)
            )

            #Get the instance, and the name
            if destination == "project":
                kanban_card_submit.project = project.objects.get(project_id=location_id)
                kanban_card_submit.kanban_card_text = "PRO" + location_id + " - " + kanban_card_submit.project.project_name
            elif destination == "task":
                kanban_card_submit.task = task.objects.get(task_id=location_id)
                kanban_card_submit.kanban_card_text = "TASK" + location_id + " - " + kanban_card_submit.task.task_short_description
            elif destination == "requirement":
                kanban_card_submit.requirement = requirement.objects.get(requirement_id=location_id)
                kanban_card_submit.kanban_card_text = "REQ" + location_id + " - " + kanban_card_submit.requirement.requirement_title
            else:
                #Oh no, something went wrong.
                return HttpResponseBadRequest("Sorry, that type of destination does not exist")

            kanban_card_submit.save()

            # Let's return the CARD back so that the user does not have to refresh
            t = loader.get_template('NearBeach/kanban/kanban_card_information.html')

            c = {
                'kanban_card_submit': kanban_card_submit,
            }

            return HttpResponse(t.render(c, request))
        else:
            print(form.errors)
            return HttpResponseBadRequest("BAD FORM")


    #Get data
    project_results = project.objects.filter(
        is_deleted="FALSE",
        project_status__in=('New','Open'),
    )
    task_results = task.objects.filter(
        is_deleted="FALSE",
        task_status__in=('New','Open'),
    )
    requirement_results = requirement.objects.filter(
        is_deleted="FALSE",
        #There is no requirement status - BUG275
    )

    t = loader.get_template('NearBeach/kanban/kanban_new_link.html')

    # context
    c = {
        'project_results': project_results,
        'task_results': task_results,
        'requirement_results': requirement_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'kanban_new_link_form': kanban_new_link_form(
            kanban_board_id=kanban_board_id
        )
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def kanban_properties(request,kanban_board_id):
    permission_results = return_user_permission_level(request, None,['kanban'])

    if permission_results['kanban'] < 4:
        return HttpResponseRedirect(reverse('permission_denied'))



    """
    If this requirement is connected to a requirement, then the user should NOT edit the properties, as it is a
    SET Designed module.
    """
    kanban_board_results = kanban_board.objects.get(kanban_board_id=kanban_board_id)
    if kanban_board_results.requirement:
        return HttpResponseBadRequest("Sorry, but users are not permitted to edit a Requirement Kanban Board.")

    if request.method == "POST":
        received_json_data = json.loads(request.body)

        #Update title
        kanban_board_results.kanban_board_name = str(received_json_data["kanban_board_name"])
        kanban_board_results.save()

        #Update the sort order for the columns
        for row in range(0, received_json_data["columns"]["length"]):
            kanban_column_update = kanban_column.objects.get(kanban_column_id=received_json_data["columns"][str(row)]["id"])
            kanban_column_update.kanban_column_sort_number = row
            kanban_column_update.save()

        # Update the sort order for the columns
        for row in range(0, received_json_data["levels"]["length"]):
            kanban_level_update = kanban_level.objects.get(kanban_level_id=received_json_data["levels"][str(row)]["id"])
            kanban_level_update.kanban_level_sort_number = row
            kanban_level_update.save()

        #Return blank page
        t = loader.get_template('NearBeach/blank.html')
        c={}
        return HttpResponse(t.render(c, request))



    #Get SQL
    kanban_column_results = kanban_column.objects.filter(
        is_deleted="FALSE",
        kanban_board_id=kanban_board_id,
    ).order_by('kanban_column_sort_number')
    kanban_level_results = kanban_level.objects.filter(
        is_deleted="FALSE",
        kanban_board_id=kanban_board_id,
    ).order_by('kanban_level_sort_number')

    t = loader.get_template('NearBeach/kanban/kanban_properties.html')

    # context
    c = {
        'kanban_board_id': kanban_board_id,
        'kanban_column_results': kanban_column_results,
        'kanban_level_results': kanban_level_results,
        'kanban_board_results': kanban_board_results,
        'kanban_properties_form': kanban_properties_form(initial={
            'kanban_board_name': kanban_board_results.kanban_board_name,
        }),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))





def login(request):
    """
	For some reason I can not use the varable "login_form" here as it is already being used.
	Instead I will use the work form.
	
	The form is declared at the start and filled with either the POST data OR nothing. If this
	process is called in POST, then the form will be checked and if it passes the checks, the
	user will be logged in.
	
	If the form is not in POST (aka GET) OR fails the checks, then it will create the form with
	the relevant errors.
	"""
    form = login_form(request.POST or None)
    print("LOGIN REQUEST")

    # reCAPTCHA
    RECAPTCHA_PUBLIC_KEY = ''
    RECAPTCHA_PRIVATE_KEY = ''
    if hasattr(settings, 'RECAPTCHA_PUBLIC_KEY') and hasattr(settings, 'RECAPTCHA_PRIVATE_KEY'):
        RECAPTCHA_PUBLIC_KEY = settings.RECAPTCHA_PUBLIC_KEY
        RECAPTCHA_PRIVATE_KEY = settings.RECAPTCHA_PRIVATE_KEY

    # POST
    if request.method == 'POST':
        print("POST")
        if form.is_valid():
            """
			Method
			~~~~~~
			1.) Collect the variables
			2.) IF reCAPTCHA is enabled, then process login through that
				statement
				IF it is not, proceed to verify login
			3.) If it all fails, it will just go back to the login screen.
			"""
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            print("DATA EXTRACTED")

            if hasattr(settings, 'RECAPTCHA_PUBLIC_KEY') and hasattr(settings, 'RECAPTCHA_PRIVATE_KEY'):
                """
				As the Google documentation states. I have to send the request back to
				the given URL. It gives back a JSON object, which will contain the
				success results.
				
				Method
				~~~~~~
				1.) Collect the variables
				2.) With the data - encode the variables into URL format
				3.) Send the request to the given URL
				4.) The response will open and store the response from GOOGLE
				5.) The results will contain the JSON Object
				"""
                recaptcha_response = request.POST.get('g-recaptcha-response')
                url = 'https://www.google.com/recaptcha/api/siteverify'
                values = {
                    'secret': RECAPTCHA_PRIVATE_KEY,
                    'response': recaptcha_response
                }
                response = urlopen(url, urllib.parse.urlencode(values).encode('utf8'))
                result = json.load(response)

                print(result)

                # Check to see if the user is a robot. Success = human
                if result['success']:
                    user = auth.authenticate(username=username, password=password)
                    auth.login(request, user)

            else:
                user = auth.authenticate(username=username, password=password)
                auth.login(request, user)

                #is_admin(request)

            # Just double checking. :)
            if request.user.is_authenticated:
                print("User Authenticated")
                """
                The user has been authenticated. Now the system will store the user's permissions and group 
                into cookies. :)
                
                First Setup
                ~~~~~~~~~~~
                If permission_set with id of 1 does not exist, go through first stage setup.
                """
                if not permission_set.objects.all():
                    #Create administration permission_set
                    submit_permission_set = permission_set(
                        permission_set_name="Administration Permission Set",
                        administration_assign_user_to_group=4,
                        administration_create_group=4,
                        administration_create_permission_set=4,
                        administration_create_user=4,
                        assign_campus_to_customer=4,
                        associate_project_and_task=4,
                        bug=4,
                        bug_client=4,
                        customer=4,
                        email=4,
                        invoice=4,
                        invoice_product=4,
                        kanban=4,
                        kanban_card=4,
                        opportunity=4,
                        organisation=4,
                        organisation_campus=4,
                        project=4,
                        quote=4,
                        requirement=4,
                        requirement_link=4,
                        task=4,
                        tax=4,
                        template=4,
                        document=1,
                        contact_history=1,
                        kanban_comment=1,
                        project_history=1,
                        task_history=1,
                        change_user=request.user,
                    )
                    submit_permission_set.save()

                    #Create admin group
                    submit_group = group(
                        group_name="Administration",
                        change_user=request.user,
                    )
                    submit_group.save()

                    #Add user to admin group
                    submit_user_group = user_group(
                        username=request.user,
                        group=group.objects.get(group_id=1),
                        permission_set=permission_set.objects.get(permission_set_id=1),
                        change_user=request.user,
                    )
                    submit_user_group.save()

                request.session['is_superuser'] = request.user.is_superuser

                return HttpResponseRedirect(reverse('alerts'))
            else:
                print("User not authenticated")
        else:
            print(form.errors)

    # load template
    t = loader.get_template('NearBeach/login.html')

    # context
    c = {
        'login_form': form,
        'RECAPTCHA_PUBLIC_KEY': RECAPTCHA_PUBLIC_KEY,
    }

    return HttpResponse(t.render(c, request))


def logout(request):
    # log the user out and go to login page
    auth.logout(request)
    return HttpResponseRedirect(reverse('login'))


@login_required(login_url='login')
def my_profile(request):
    permission_results = return_user_permission_level(request, None,None)

    #Data required in both POST and GET
    about_user_results=about_user.objects.filter(
        is_deleted="FALSE",
        user=request.user,
    ).order_by('-date_created')
    if about_user_results:
        about_user_text = about_user_results[0].about_user_text
    else:
        about_user_text = ""

    user_instance = User.objects.get(id=request.user.id)

    if request.method == "POST":
        """
        User Information
        ~~~~~~~~~~~~~~~~
        We want to always update the user information. Give the User the option to also update
        their password.
        """
        form = my_profile_form(request.POST)
        if form.is_valid():
            user_instance.first_name=form.cleaned_data['first_name']
            user_instance.last_name=form.cleaned_data['last_name']
            user_instance.email=form.cleaned_data['email']
            user_instance.save()

            password1 = form.cleaned_data['password1']
            password2 = form.cleaned_data['password2']

            if password1 == password2:
                # Change passwords
                if not password1 == "":
                    user_instance = User.objects.get(id=request.user.id)
                    user_instance.set_password(password1)
                    user_instance.save()

        else:
            print(form.errors)

        """
        About User Text
        ~~~~~~~~~~~~~~~
        If there is a difference between the current about user and what the user has submitted,
        we want to update the database.
        If there is no change - we will ignore. No need to flood the database with the exact same data over
        and over again.
        """
        form = about_user_form(request.POST)
        if form.is_valid():
            if not about_user_text == form.cleaned_data['about_user_text'] and not about_user_text == None:
                about_user_text = form.cleaned_data['about_user_text']

                about_user_submit = about_user(
                    change_user=request.user,
                    about_user_text=about_user_text,
                    user_id=request.user.id
                )
                about_user_submit.save()
        else:
            print(form.errors)

    #Get data
    project_results = project.objects.filter(
        is_deleted="FALSE",
        project_id__in=assigned_user.objects.filter(
            is_deleted="FALSE",
            user_id=request.user.id,
        ).values('project_id').distinct()
    )

    #Initialise about user form, if there is no about_user use a blank ""


    # load template
    t = loader.get_template('NearBeach/my_profile.html')

    # context
    c = {
        'project_results': project_results,
        'my_profile_form': my_profile_form(
            instance=user_instance,
        ),
        'about_user_form': about_user_form(initial={
            'about_user_text': about_user_text,
        }),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def new_bug_client(request):
    permission_results = return_user_permission_level(request, None, 'bug_client')

    if permission_results['bug_client'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))
    form_errors = ''
    if request.method == "POST":
        form = bug_client_form(request.POST)
        if form.is_valid():
            #Get required data
            bug_client_name = form.cleaned_data['bug_client_name']
            list_of_bug_client = form.cleaned_data['list_of_bug_client']
            bug_client_url = form.cleaned_data['bug_client_url']

            #Test the link first before doing ANYTHING!
            try:
                url = bug_client_url + list_of_bug_client.bug_client_api_url + 'version'
                print(url)
                response = urlopen(url)
                data = json.load(response)
                print("Got the JSON")

                bug_client_submit = bug_client(
                    bug_client_name = bug_client_name,
                    list_of_bug_client = list_of_bug_client,
                    bug_client_url = bug_client_url,
                    change_user=request.user,
                )
                bug_client_submit.save()
                return HttpResponseRedirect(reverse('bug_client_list'))
            except:
                form_errors = "Could not connect to the API"


        else:
            print(form.errors)
            form_errors(form.errors)

    # load template
    t = loader.get_template('NearBeach/new_bug_client.html')

    # context
    c = {
        'bug_client_form': bug_client_form(),
        'form_errors': form_errors,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))

@login_required(login_url='login')
def new_campus(request, location_id, destination):
    permission_results = return_user_permission_level(request, None, 'organisation_campus')

    if permission_results['organisation_campus'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    """
	If the user is not logged in, we want to send them to the login page.
	This function should be in ALL webpage requests except for login and
	the index page
	"""
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse('login'))

    if request.method == 'POST':
        form = new_campus_form(request.POST)
        if form.is_valid():
            # Get instances
            region_instance = list_of_country_region.objects.get(
                region_id=request.POST.get('country_and_regions')
            )

            campus_nickname = form.cleaned_data['campus_nickname']
            campus_phone = form.cleaned_data['campus_phone']
            campus_fax = form.cleaned_data['campus_fax']
            campus_address1 = form.cleaned_data['campus_address1']
            campus_address2 = form.cleaned_data['campus_address2']
            campus_address3 = form.cleaned_data['campus_address3']
            campus_suburb = form.cleaned_data['campus_suburb']

            #organisation = organisation.objects.get(organisation_id)

            # BUG - some simple validation should go here?

            # Submitting the data
            submit_form = campus(
                #organisation_id=organisation,
                campus_nickname=campus_nickname,
                campus_phone=campus_phone,
                campus_fax=campus_fax,
                campus_address1=campus_address1,
                campus_address2=campus_address2,
                campus_address3=campus_address3,
                campus_suburb=campus_suburb,
                campus_region_id=region_instance,
                campus_country_id=region_instance.country_id,
                change_user = request.user,
            )
            if destination == "organisation":
                submit_form.organisation_id = organisation.objects.get(organisation_id=location_id)
            else:
                submit_form.customer = customer.objects.get(customer_id=location_id)
            submit_form.save()

            #Get the coordinates and update them into the system
            update_coordinates(submit_form.campus_id)

            if destination == "organisation":
                return HttpResponseRedirect(reverse(organisation_information, args={location_id}))
            else:
                return HttpResponseRedirect(reverse(customer_information, args={location_id}))
        else:
            print(form.errors)
            return HttpResponseRedirect(reverse(new_campus, args={location_id,destination}))

    # SQL
    countries_results = list_of_country.objects.all().order_by('country_name')
    countries_regions_results = list_of_country_region.objects.all().order_by('region_name')

    # load template
    t = loader.get_template('NearBeach/new_campus.html')

    # context
    c = {
        'location_id': location_id,
        'destination': destination,
        'new_campus_form': new_campus_form(),
        'countries_results': countries_results,
        'countries_regions_results': countries_regions_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def new_customer(request, organisation_id):
    permission_results = return_user_permission_level(request, None, 'customer')

    if permission_results['customer'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    form_errors = ''
    if request.method == 'POST':
        form = new_customer_form(request.POST)
        if form.is_valid():
            customer_title = form.cleaned_data['customer_title']
            customer_first_name = form.cleaned_data['customer_first_name']
            customer_last_name = form.cleaned_data['customer_last_name']
            customer_email = form.cleaned_data['customer_email']


            organisation_id = form.cleaned_data['organisation_id']

            submit_form = customer(
                customer_title=customer_title,
                customer_first_name=customer_first_name,
                customer_last_name=customer_last_name,
                customer_email=customer_email,
                organisation_id=organisation_id,
                change_user=request.user,
            )

            # BUG - no validation process to see if there exists a customer already :(
            submit_form.save()

            return HttpResponseRedirect(reverse(customer_information, args={submit_form.customer_id}))
        else:
            form_errors = form.errors
    else:
        initial = {
            'organisation_id': organisation_id,
        }

        form = new_customer_form(initial=initial)


    # load template
    t = loader.get_template('NearBeach/new_customer.html')



    # context
    c = {
        #'new_customer_form': new_customer_form(initial=initial),
        'new_customer_form': form,
        'organisation_id': organisation_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'form_errors': form_errors,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def new_kanban_board(request):
    permission_results = return_user_permission_level(request, None, 'kanban')

    if permission_results['kanban'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        form = kanban_board_form(request.POST)
        if form.is_valid():
            #Create the new board
            kanban_board_submit = kanban_board(
                kanban_board_name=form.cleaned_data['kanban_board_name'],
                change_user=request.user,
            )
            kanban_board_submit.save()

            #Create the levels for the board
            column_count = 1
            for line in form.cleaned_data['kanban_board_column'].split('\n'):
                kanban_column_submit = kanban_column(
                    kanban_column_name=line,
                    kanban_column_sort_number=column_count,
                    kanban_board=kanban_board_submit,
                    change_user=request.user,
                )
                kanban_column_submit.save()
                column_count = column_count + 1


            level_count = 1
            for line in form.cleaned_data['kanban_board_level'].split('\n'):
                kanban_level_submit = kanban_level(
                    kanban_level_name=line,
                    kanban_level_sort_number=level_count,
                    kanban_board=kanban_board_submit,
                    change_user=request.user,
                )
                kanban_level_submit.save()
                level_count = level_count + 1

            #Send you to the kanban information center
            return HttpResponseRedirect(reverse('kanban_information', args={kanban_board_submit.kanban_board_id}))

        else:
            print(form.errors)
            return HttpResponseBadRequest(form.errors)

    t = loader.get_template('NearBeach/new_kanban_board.html')

    c = {
        'kanban_board_form': kanban_board_form(initial={
            'kanban_board_column': 'Backlog\nIn Progress\nCompleted',
            'kanban_board_level': 'Sprint 1\nSprint 2',
        }),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],

    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def new_opportunity(request, location_id,destination):
    permission_results = return_user_permission_level(request, None, 'opportunity')

    if permission_results['opportunity'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    # POST or None
    if request.method == 'POST':
        form = new_opportunity_form(request.POST)
        if form.is_valid():
            current_user = request.user
            # Start saving the data in the form
            opportunity_name = form.cleaned_data['opportunity_name']
            opportunity_description = form.cleaned_data['opportunity_description']
            currency_id = form.cleaned_data['currency_id']
            opportunity_amount = form.cleaned_data['opportunity_amount']
            amount_type_id = form.cleaned_data['amount_type_id']
            opportunity_success_probability = form.cleaned_data['opportunity_success_probability']
            lead_source_id = form.cleaned_data['lead_source_id']
            select_groups = form.cleaned_data['select_groups']
            select_users = form.cleaned_data['select_users']
            opportunity_expected_close_date = form.cleaned_data['opportunity_expected_close_date']



            """
			Some dropdown boxes will need to have instances made from the values.
			"""
            stage_of_opportunity_instance = list_of_opportunity_stage.objects.get(
                opportunity_stage_id=request.POST.get('opportunity_stage')
            )

            """
			SAVE THE DATA
			"""
            submit_opportunity = opportunity(
                opportunity_name=opportunity_name,
                opportunity_description=opportunity_description,
                currency_id=currency_id,
                opportunity_amount=opportunity_amount,
                amount_type_id=amount_type_id,
                opportunity_success_probability=opportunity_success_probability,
                lead_source_id=lead_source_id,
                opportunity_expected_close_date=opportunity_expected_close_date,
                opportunity_stage_id=stage_of_opportunity_instance,
                user_id=current_user,
                change_user=request.user,
            )
            """
            We ignore the destination at this part. A user might have tried to create the opportunity from the organisation
            however have the change of mind when filling out the form. This short method checks to see if there is a
            customer id. If there is one, then it will assign the opportunity to the customer.
            """
            customer_id = request.POST.get('customer_id')
            if customer_id.isdigit():
                customer_instance = customer.objects.get(customer_id=request.POST.get('customer_id'))
                submit_opportunity.customer_id = customer_instance
                #If a customer has a null for an organisation it will pass through as null
                submit_opportunity.organisation_id = customer_instance.organisation_id
            else:
                """
                try:
                    organisation_instance = organisation.objects.get(organisation_id=form.cleaned_data['organisation_id'])
                    submit_opportunity.organisation_id = organisation_instance
                except:
                    organisation_instance = None
                    submit_opportunity.organisation_id = organisation_instance
                """
                organisations_instance = form.cleaned_data['organisation_id']
                if organisations_instance:
                    submit_opportunity.organisation_id = organisations_instance
            submit_opportunity.save()
            opportunity_instance = opportunity.objects.get(opportunity_id=submit_opportunity.opportunity_id)

            """
            Permissions granting
            """
            give_all_access = True

            if (select_groups):
                give_all_access = False


                for row in select_groups:
                    group_instance = group.objects.get(group_name=row)
                    permission_save = opportunity_permission(
                        opportunity_id=opportunity_instance,
                        group_id=group_instance,
                        change_user=request.user,
                    )
                    permission_save.save()

            if (select_users):
                give_all_access = False

                for row in select_users:
                    assigned_user_instance = auth.models.User.objects.get(username=row)
                    permission_save = opportunity_permission(
                        opportunity_id=opportunity_instance,
                        assigned_user=assigned_user_instance,
                        change_user=request.user,
                    )
                    permission_save.save()

            if (give_all_access):
                permission_save = opportunity_permission(
                    opportunity_id=opportunity_instance,
                    all_user='TRUE',
                    change_user=request.user,
                )
                permission_save.save()

            """
			Now we go to the opportunity information page so the user can start
			inputting the require information (like document), and task.
			"""
            return HttpResponseRedirect(reverse(opportunity_information, args={submit_opportunity.opportunity_id}))
        else:
            print(form.errors)


    # load template
    t = loader.get_template('NearBeach/new_opportunity.html')

    # DATA
    customer_results = customer.objects.all()
    opportunity_stage_results = list_of_opportunity_stage.objects.filter(is_deleted="FALSE")

    # context
    c = {
        'new_opportunity_form': new_opportunity_form(),
        'customer_results': customer_results,
        'location_id': location_id,
        'destination': destination,
        'opportunity_stage_results': opportunity_stage_results,
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'destination': destination,
        'location_id': location_id,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def new_organisation(request):
    permission_results = return_user_permission_level(request, None, 'organisation')

    if permission_results['organisation'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))
    """
	To stop duplicates in the system, the code will quickly check to see if
	there is already a company that has either one of the following;
	-- same name
	-- same website
	-- same contact email.
	
	If one of these conditions are met then the user will be returned to the
	form and shown the possible duplicates. If the user accepts this, then
	the organisation is created.	
	"""
    form_errors = ""
    form = new_organisation_form(request.POST or None)
    duplicate_results = None
    if request.method == 'POST':
        if form.is_valid():
            organisation_name = form.cleaned_data['organisation_name']
            organisation_email = form.cleaned_data['organisation_email']
            organisation_website = form.cleaned_data['organisation_website']

            duplicate_results = organisation.objects.filter(
                Q(organisation_name=organisation_name) | Q(organisation_email=organisation_email) | Q(
                    organisation_website=organisation_website))

            """
			If the user has clicked that they accept the duplicate OR if there
			are NO duplicates, just make the organisation :)
			"""
            if ((duplicate_results.count() == 0) or (request.POST.get("save_duplicate"))):
                # Save the form data
                submit_form = organisation(
                    organisation_name=organisation_name,
                    organisation_email=organisation_email,
                    organisation_website=organisation_website,
                    change_user=request.user,
                )
                submit_form.save()

                return HttpResponseRedirect(reverse(organisation_information, args={submit_form.organisation_id}))
        else:
            form_errors = form.errors

    """
	Now that we have determined if the organisation should be saved or not
	we are left with the only options;
	1.) There was no organisation to save
	2.) there was a duplicate organisation and we are asking the user about it
	"""
    # load template
    t = loader.get_template('NearBeach/new_organisation.html')

    # Define the duplication count
    duplication_count = 0;
    if not duplicate_results == None:
        duplication_count = duplicate_results.count()

    # context
    c = {
        'new_organisation_form': form,
        'duplicate_results': duplicate_results,
        'duplication_count': duplication_count,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'form_errors': form_errors,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def new_project(request, location_id='', destination=''):
    permission_results = return_user_permission_level(request, None, 'project')

    if permission_results['project'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        form = new_project_form(request.POST)
        if form.is_valid():
            print("Form is valid")
            project_name = form.cleaned_data['project_name']
            project_description = form.cleaned_data['project_description']
            organisation_id_form = form.cleaned_data['organisation_id']

            submit_project = project(
                project_name=project_name,
                project_description=project_description,
                project_start_date=form.cleaned_data['project_start_date'],
                project_end_date=form.cleaned_data['project_end_date'],
                project_status='New',
                change_user=request.user,
            )
            if organisation_id_form:
                submit_project.organisation_id=organisation_id_form

            # Submit the data
            submit_project.save()

            """
			Once the new project has been created, we will obtain a 
			primary key. Using this new primary key we will allocate
			group to the new project.
			"""
            assigned_to_groups = form.cleaned_data['assigned_groups']

            for row in assigned_to_groups:
                submit_group = project_group(
                    project_id_id=submit_project.pk,
                    group_id_id=row.group_id,
                    change_user=request.user,
                )
                submit_group.save()
            """
            If the destination is CUSTOMER, then we assign the project_customer to that customer.
            If the destination is connected to OPPORTUNITY, then we assign it to the opportunity.
            """
            print("CURRENT DESTINATION IS: " + str(destination))
            if destination == "customer":
                customer_instance = customer.objects.get(customer_id=location_id)
                save_project_customer = project_customer(
                    project_id=submit_project,
                    customer_id=customer_instance,
                    change_user=request.user,
                )
                save_project_customer.save()
            elif destination == "opportunity":
                opportunity_instance = opportunity.objects.get(opportunity_id=location_id)
                save_project_opportunity = project_opportunity(
                    project_id=submit_project,
                    opportunity_id=opportunity_instance,
                    change_user=request.user,
                )
                save_project_opportunity.save()

            """
            We want to return the user to the original location. This is dependent on the destination
            """
            print("New project now compeleted - going to location.")
            if destination == "organisation":
                return HttpResponseRedirect(reverse(organisation_information, args={location_id}))
            elif destination == "customer":
                return HttpResponseRedirect(reverse(customer_information, args={location_id}))
            elif destination == "opportunity":
                return HttpResponseRedirect(reverse(opportunity_information, args={location_id}))
            else:
                return HttpResponseRedirect(reverse(project_information, args={submit_project.pk}))
        else:
            print("Form is not valid")
            print(form.errors)

    # Obtain the group the user is associated with
    current_user = request.user
    cursor = connection.cursor()

    groups_results = group.objects.filter(
        is_deleted="FALSE",
        group_id__in=user_group.objects.filter(
            is_deleted="FALSE",
            username_id=current_user.id
        ).values('group_id')
    )

    organisations_results = organisation.objects.filter(is_deleted='FALSE')


    #FIGURE OUT HOW TO GET ORGANISATION HERE!
    if destination == "" or destination == None:
        organisation_id = None
        customer_id = None
        opportunity_id = None
    elif destination == "organisation":
        organisation_id = location_id
        customer_id = None
        opportunity_id = None
    elif destination == "customer":
        customer_instance = customer.objects.get(customer_id=location_id)

        organisation_id = customer.organisation_id
        customer_id = customer.customer_id
        opportunity_id = None
    elif destination == "opportunity":
        opportunity_instance = opportunity.objects.get(opportunity_id=location_id)

        organisation_id = opportunity_instance.organisation_id
        customer_id = opportunity_instance.customer_id
        opportunity_id = opportunity_instance.opportunity_id


    # Load the template
    t = loader.get_template('NearBeach/new_project.html')

    print(request.user.id)

    # context
    c = {
        'new_project_form': new_project_form(initial={
            'organisation_id': organisation_id,
        }),
        'groups_results': groups_results,
        'groups_count': groups_results.__len__(),
        'opportunity_id': opportunity_id,
        'organisations_count': organisations_results.count(),
        'organisation_id': organisation_id,
        'customer_id': customer_id,
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'destination': destination,
        'location_id': location_id,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def new_quote(request,destination,primary_key):
    permission_results = return_user_permission_level(request, None,'quote')

    if permission_results['quote'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        form = new_quote_form(request.POST)
        if form.is_valid():
            quote_title=form.cleaned_data['quote_title']
            quote_terms=form.cleaned_data['quote_terms']
            quote_stage_id=form.cleaned_data['quote_stage_id']
            customer_notes=form.cleaned_data['customer_notes']
            select_groups = form.cleaned_data['select_groups']
            select_users = form.cleaned_data['select_users']

            # Create the final start/end date fields
            quote_valid_till = convert_to_utc(
                int(form.cleaned_data['quote_valid_till_year']),
                int(form.cleaned_data['quote_valid_till_month']),
                int(form.cleaned_data['quote_valid_till_day']),
                int(form.cleaned_data['quote_valid_till_hour']),
                int(form.cleaned_data['quote_valid_till_minute']),
                form.cleaned_data['quote_valid_till_meridiems']
            )
            quote_stage_instance = list_of_quote_stage.objects.get(quote_stage_id=quote_stage_id.quote_stage_id)

            submit_quotes = quote(
                quote_title=quote_title,
                quote_terms=quote_terms,
                quote_stage_id=quote_stage_instance,
                customer_notes=customer_notes,
                quote_valid_till=quote_valid_till,
                change_user=request.user
            )
            """
            ADD CODE HERE
            If the user does not have the access to approve quote, then the quote approval
            sticks to draft and they will not be able to turn it into an INVOICE.
            If however the user DOES have access to approve quote, then the quote approval
            sticks to approved and they can instantly turn the quote into an INVOICE.
            This is an automatic process - no user input needed
            
            
            EXCEPT I HAVE TO WRITE THE CODE. So by default I am just turning it to the default value.
            """
            submit_quotes.quote_approval_status_id='APPROVED'


            """
            Link the quote to the correct project/task/opportunity
            """
            if destination=='project':
                submit_quotes.project_id = project.objects.get(project_id=primary_key)
            elif destination=='task':
                submit_quotes.task_id = task.objects.get(task_id=primary_key)
            elif destination=='customer':
                submit_quotes.customer_id = customer.objects.get(customer_id=primary_key)
            elif destination=='organisation':
                submit_quotes.organisation_id = organisation.objects.get(organisation_id=primary_key)
            else:
                submit_quotes.opportunity_id = opportunity.objects.get(opportunity_id=primary_key)

            submit_quotes.save()

            """
            Permissions
            ~~~~~~~~~~~
            If the user left BOTH the user and group permissions empty then we give everyone access.
            Otherwise we will loop through BOTH and add the correct permissions.
            """
            give_all_access = True

            if (select_groups):
                give_all_access = False

                for row in select_groups:
                    group_instance = group.objects.get(group_name=row)
                    permission_save = quote_permission(
                        quote_id=submit_quotes.quote_id,
                        group_id=group_instance,
                        change_user=request.user,
                    )
                    permission_save.save()

            if (select_users):
                give_all_access = False

                for row in select_users:
                    assigned_user_instance = auth.models.User.objects.get(username=row)
                    permission_save = quote_permission(
                        quote_id=submit_quotes.quote_id,
                        assigned_user=assigned_user_instance,
                        change_user=request.user,
                    )
                    permission_save.save()

            if (give_all_access):
                permission_save = quote_permission(
                    quote_id=submit_quotes.quote_id,
                    all_user='TRUE',
                    change_user=request.user,
                )
                permission_save.save()

            #Now to go to the quote information page
            return HttpResponseRedirect(reverse(quote_information, args={submit_quotes.quote_id}))

        else:
            print(form.errors)

    end_date = datetime.datetime.now()+timedelta(14)


    # Load the template
    t = loader.get_template('NearBeach/new_quote.html')

    # context
    c = {
        'new_quote_form': new_quote_form,
        'primary_key': primary_key,
        'destination': destination,
        'end_year': end_date.year,
        'end_month': end_date.month,
        'end_day': end_date.day,
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))

@login_required(login_url='login')
def new_quote_template(request):
    permission_results = return_user_permission_level(request, None, 'templates')

    if permission_results['templates'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    # Define if the page is loading in POST
    if request.method == "POST":
        #User has requested new quote template
        quote_template_submit=quote_template(
            change_user_id=request.user.id,
            quote_template_description = "Quote Template",
            template_css="""
            .table_header {
                font-family: "Trebuchet MS", Arial, Helvetica, sans-serif;
                border-collapse: collapse;
                width: 100%;
            }
            
            .table_header {
                border: 1px solid #ddd;
                padding: 8px;
            }
            
            .table_header {
                padding-top: 12px;
                padding-bottom: 12px;
                text-align: left;
                background-color: #4CAF50;
                color: white;
            }
            
            table td, table td * {
                vertical-align: top;
            }
            """,
            header="NearBeach Quote Number {{ quote_id }}",
            company_letter_head="<p>NearBeach Incorporated<br />Melbourne 3000<br />Australia</p>",
            payment_terms="Please pay within 30 days",
            notes="{{ quote_terms }}",
            organisation_details="""
                <p>{{ organisation_name }}<br />
                {{ billing_address1 }}<br />
                {{ billing_address2 }}<br />
                {{ billing_address3 }}<br />
                {{ billing_suburb }} {{ billing_postcode }}<br />
                {{ billing_region }}<br />
                {{ billing_country }}</p>
            """,
            product_line = "Temp product line",
            service_line = "Temp service line",
            payment_method="""
            <table>
            <tbody>
            <tr style="height: 18px;">
            <td style="width: 50%; height: 18px;">Account</td>
            <td style="width: 50%; height: 18px;">0000 0000</td>
            </tr>
            <tr style="height: 18px;">
            <td style="width: 50%; height: 18px;">BSB</td>
            <td style="width: 50%; height: 18px;">000 000</td>
            </tr>
            <tr style="height: 18px;">
            <td style="width: 50%; height: 18px;">Acount Name</td>
            <td style="width: 50%; height: 18px;">NearBeach Holdings</td>
            </tr>
            </tbody>
            </table>
            """,
            footer="{{ page_number }}",
        )
        quote_template_submit.save()

        #Send back the quote number
        json_data = {}
        json_data['quote_template_id'] = quote_template_submit.pk
        #json_data['quote_template_id'] = '1'

        return JsonResponse(json_data)
    else:
        return HttpResponseBadRequest("Sorry, but new template can only be requested by a post command")



@login_required(login_url='login')
def new_task(request, location_id='', destination=''):
    permission_results = return_user_permission_level(request, None, 'task')

    if permission_results['task'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    # Define if the page is loading in POST
    if request.method == "POST":
        form = new_task_form(request.POST)
        if form.is_valid():
            task_short_description = form.cleaned_data['task_short_description']
            task_long_description = form.cleaned_data['task_long_description']
            organisation_id_form = form.cleaned_data['organisation_id']


            submit_task = task(
                task_short_description=task_short_description,
                task_long_description=task_long_description,
                #organisation_id=organisation_id_form,
                task_start_date=form.cleaned_data['task_start_date'],
                task_end_date=form.cleaned_data['task_end_date'],
                task_status='New',
                change_user = request.user,
            )

            if organisation_id_form:
                submit_task.organisation_id = organisation_id_form

            # Submit the data
            submit_task.save()

            """
			Once the new project has been created, we will obtain a 
			primary key. Using this new primary key we will allocate
			group to the new project.
			"""
            assigned_to_groups = form.cleaned_data['assigned_groups']

            for row in assigned_to_groups:
                submit_group = task_group(
                    task_id_id=submit_task.pk,
                    group_id_id=row.group_id,
                    change_user=request.user,
                )
                submit_group.save()

            """
            If the destination is CUSTOMER, then we assign the project_customer to that customer.
            If the destination is connected to OPPORTUNITY, then we assign it to the opportunity.
            """
            if destination == "customer":
                customer_instance = customer.objects.get(customer_id=location_id)
                save_project_customer = task_customer(
                    task_id=submit_task,
                    customer_id=customer_instance,
                    change_user=request.user,
                )
                save_project_customer.save()
            elif destination == "opportunity":
                opportunity_instance = opportunity.objects.get(opportunity_id=location_id)
                save_project_opportunity = task_opportunity(
                    task_id=submit_task,
                    opportunity_id=opportunity_instance,
                    change_user=request.user,
                )
                save_project_opportunity.save()

            """
            We want to return the user to the original location. This is dependent on the destination
            """
            if destination == "organisation":
                return HttpResponseRedirect(reverse(organisation_information, args={location_id}))
            elif destination == "customer":
                return HttpResponseRedirect(reverse(customer_information, args={location_id}))
            elif destination == "opportunity":
                return HttpResponseRedirect(reverse(opportunity_information, args={location_id}))
            else:
                return HttpResponseRedirect(reverse(task_information, args={submit_task.pk}))
                # Lets go back to the customer
    else:
        # Obtain the group the user is associated with
        groups_results = group.objects.filter(
            is_deleted="FALSE",
            group_id__in=user_group.objects.filter(
                is_deleted="FALSE",
                username_id=request.user.id
            ).values('group_id')
        )

        organisations_results = organisation.objects.filter(is_deleted='FALSE')

        # Setup dates for initalising
        today = datetime.datetime.now()
        next_week = today + datetime.timedelta(days=31)

        """
		We need to do some basic formulations with the hour and and minutes.
		For the hour we need to find all those who are in the PM and
		change both the hour and meridiem accordingly.
		For the minute, we have to create it in 5 minute blocks.
		"""
        hour = today.hour
        minute = int(5 * round(today.minute / 5.0))
        meridiems = 'AM'

        if hour > 12:
            hour = hour - 12
            meridiems = 'PM'
        elif hour == 0:
            hour = 12

        #FIGURE OUT HOW TO GET ORGANISATION HERE!
        if destination == "" or destination == None:
            organisation_id = None
            customer_id = None
            opportunity_id = None
        elif destination == "organisation":
            organisation_id = location_id
            customer_id = None
            opportunity_id = None
        elif destination == "customer":
            customer_instance = customer.objects.get(customer_id=location_id)

            organisation_id = customer.organisation_id
            customer_id = customer.customer_id
            opportunity_id = None
        elif destination == "opportunity":
            opportunity_instance = opportunity.objects.get(opportunity_id=location_id)

            organisation_id = opportunity_instance.organisation_id
            customer_id = opportunity_instance.customer_id
            opportunity_id = opportunity_instance.opportunity_id


        # Loaed the template
        t = loader.get_template('NearBeach/new_task.html')

        c = {
            'new_task_form': new_task_form(
                initial={
                    'organisation_id': organisation_id,
                }),
            'groups_results': groups_results,
            'groups_count': groups_results.__len__(),
            'organisation_id': organisation_id,
            'organisations_count': organisation.objects.filter(is_deleted='FALSE').count(),
            'customer_id': customer_id,
            'opportunity_id': opportunity_id,
            'timezone': settings.TIME_ZONE,
            'location_id': location_id,
            'destination': destination,
            'new_item_permission': permission_results['new_item'],
            'administration_permission': permission_results['administration'],
        }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def opportunity_delete_permission(request, opportunity_permissions_id):
    if request.method == "POST":
        opportunity_permission_update = opportunity_permission.objects.get(opportunity_permissions_id=opportunity_permissions_id)
        opportunity_permission_update.is_deleted = "TRUE"
        opportunity_permission_update.change_user = request.user
        opportunity_permission_update.save()

        # RETURN BLANK PAGE
        t = loader.get_template('NearBeach/blank.html')

        c = {}

        return HttpResponse(t.render(c, request))

    else:
        return HttpResponseBadRequest("Sorry, this has to be through post")

@login_required(login_url='login')
def opportunity_group_permission(request, opportunity_id):
    if request.method == "POST":
        form = opportunity_group_permission_form(request.POST, group_results=group.objects.all())
        if form.is_valid():
            opportunity_permissions_submit = opportunity_permission(
                change_user=request.user,
                group_id=form.cleaned_data['group'],
                opportunity_id=opportunity.objects.get(opportunity_id=opportunity_id),
            )
            opportunity_permissions_submit.save()
        else:
            print(form.errors)

    group_permission = opportunity_permission.objects.filter(
        is_deleted="FALSE",
        opportunity_id=opportunity_id,
    ).exclude(
        group_id__isnull=True,
    )

    group_results = group.objects.filter(
        is_deleted="FALSE",
    ).exclude(
        group_id__in=group_permission.values_list('group_id')
    )

    # Loaed the template
    t = loader.get_template('NearBeach/opportunity/opportunity_group_permission.html')

    c = {
        'group_permission': group_permission,
        'group_results': group_results,
        'opportunity_permission_form': opportunity_group_permission_form(group_results=group_results),
    }

    return HttpResponse(t.render(c, request))




@login_required(login_url='login')
def opportunity_information(request, opportunity_id):
    permission_results = return_user_permission_level(request, None,'opportunity')

    if permission_results['opportunity']  == 0:
        return HttpResponseRedirect(reverse('permission_denied'))


    if request.method == "POST":
        form = opportunity_information_form(request.POST, request.FILES)
        if form.is_valid():
            current_user = request.user

            save_opportunity = opportunity.objects.get(opportunity_id=opportunity_id)

            # Save opportunity information
            save_opportunity.opportunity_name = form.cleaned_data['opportunity_name']
            save_opportunity.opportunity_description = form.cleaned_data['opportunity_description']
            save_opportunity.opportunity_amount = form.cleaned_data['opportunity_amount']
            save_opportunity.opportunity_success_probability = form.cleaned_data['opportunity_success_probability']
            save_opportunity.opportunity_expected_close_date=form.cleaned_data['opportunity_expected_close_date']
            save_opportunity.change_user=request.user

            # Instance needed
            save_opportunity.currency_id = list_of_currency.objects.get(currency_id=int(request.POST['currency_id']))
            save_opportunity.amount_type_id = list_of_amount_type.objects.get(
                amount_type_id=int(request.POST['amount_type_id']))
            save_opportunity.opportunity_stage_id = list_of_opportunity_stage.objects.get(
                opportunity_stage_id=int(request.POST['opportunity_stage_id']))


            #Save the opportunity
            save_opportunity.save()
            opportunity_instance = opportunity.objects.get(opportunity_id=opportunity_id)

            # Save the to-do if required
            next_step = form.cleaned_data['next_step']
            if not next_step == '':
                save_next_step = opportunity_next_step(
                    opportunity_id=opportunity_instance,
                    next_step_description=next_step,
                    change_user_id=request.user.id, #WHY???
                    user_id=current_user,
                )
                save_next_step.save()

            # If we need to add more users :D
            select_groups = form.cleaned_data['select_groups']
            if select_groups:
                for row in select_groups:
                    group_instance = group.objects.get(group_id=row.group_id)
                    permission_save = opportunity_permission(
                        opportunity_id=opportunity_instance,
                        group_id=group_instance,
                        user_id=current_user,
                        change_user=request.user,
                    )
                    permission_save.save()
                #Will remove the ALL USERS permissions now that we have limited the permissions
                opportunity_permission.objects.filter(
                    opportunity_id=opportunity_id,
                    all_user='TRUE',
                    is_deleted='FALSE'
                ).update(is_deleted='TRUE')

            select_users = form.cleaned_data['select_users']
            print(select_users)
            if select_users:
                for row in select_users:
                    assigned_user_instance = auth.models.User.objects.get(username=row)
                    permission_save = opportunity_permission(
                        opportunity_id=opportunity_instance,
                        assigned_user=assigned_user_instance,
                        user_id=current_user,
                        change_user=request.user,
                    )
                    permission_save.save()
                #Will remove the ALL USERS permissions now that we have limited the permissions
                opportunity_permission.objects.filter(
                    opportunity_id=opportunity_id,
                    all_user='TRUE',
                    is_deleted='FALSE'
                ).update(is_deleted='TRUE')
        else:
            print(form.errors)

    else:
        """
        We want to limit who can see what opportunity. The exception to this is for the user
        who just created the opportunity. (I should program in a warning stating that they
        might not be able to see the opportunity again unless they add themselfs to the 
        permissions list.

        The user has to meet at least one of these conditions;
        1.) User has permission
        2.) User's group has permission
        3.) All users have permission
        """
        user_groups_results = user_group.objects.filter(username=request.user)

        opportunity_permission_results = opportunity_permission.objects.filter(
            Q(
                Q(assigned_user=request.user)  # User has permission
                | Q(group_id__in=user_groups_results.values('group_id'))  # User's group have permission
                | Q(all_user='TRUE')  # All users have access
            )
            & Q(opportunity_id=opportunity_id)
        )


        if (not opportunity_permission_results):
            return HttpResponseRedirect(
                reverse(
                    permission_denied,
                )
            )


    # Data
    project_results = project_opportunity.objects.filter(
        opportunity_id=opportunity_id,
        is_deleted='FALSE',
    )
    task_results = task_opportunity.objects.filter(
        opportunity_id=opportunity_id,
        is_deleted='FALSE',
    )
    opportunity_results = opportunity.objects.get(opportunity_id=opportunity_id)
    customer_results = customer.objects.filter(organisation_id=opportunity_results.organisation_id)
    group_permissions = opportunity_permission.objects.filter(
        group_id__isnull=False,
        opportunity_id=opportunity_id,
        is_deleted='FALSE',
    ).distinct()
    user_permissions = auth.models.User.objects.filter(
        id__in=opportunity_permission.objects.filter(
            assigned_user__isnull=False,
            opportunity_id=opportunity_id,
            is_deleted='FALSE',
        ).values('assigned_user').distinct()
    )

    quote_results = quote.objects.filter(
        is_deleted='FALSE',
        opportunity_id=opportunity_id,
    )
    print(user_permissions)

    end_hour = opportunity_results.opportunity_expected_close_date.hour
    end_meridiem = u'AM'

    print(str(end_hour))

    if end_hour > 12:
        end_hour = end_hour - 12
        end_meridiem = 'PM'
    elif end_hour == 0:
        end_hour = 12

    # initial data
    initial = {
        'finish_date_year': opportunity_results.opportunity_expected_close_date.year,
        'finish_date_month': opportunity_results.opportunity_expected_close_date.month,
        'finish_date_day': opportunity_results.opportunity_expected_close_date.day,
        'finish_date_hour': end_hour,
        'finish_date_minute': opportunity_results.opportunity_expected_close_date.minute,
        'finish_date_meridiems': end_meridiem,
    }

    # Loaed the template
    t = loader.get_template('NearBeach/opportunity_information.html')

    c = {
        'opportunity_id': str(opportunity_id),
        'opportunity_information_form': opportunity_information_form(
            instance=opportunity_results,
            initial=initial,
        ),
        'opportunity_results': opportunity_results,
        'customer_results': customer_results,
        'group_permission': group_permissions,
        'user_permissions': user_permissions,
        'project_results': project_results,
        'task_results': task_results,
        'quote_results': quote_results,
        'opportunity_perm': permission_results['opportunity'],
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))




@login_required(login_url='login')
def opportunity_user_permission(request, opportunity_id):
    if request.method == "POST":
        form = opportunity_user_permission_form(request.POST, user_results=User.objects.all())
        if form.is_valid():
            opportunity_permissions_submit = opportunity_permission(
                change_user=request.user,
                assigned_user=form.cleaned_data['user'],
                opportunity_id=opportunity.objects.get(opportunity_id=opportunity_id)
            )
            opportunity_permissions_submit.save()
        else:
            print(form.errors)

    group_permission = opportunity_permission.objects.filter(
        is_deleted="FALSE",
        opportunity_id=opportunity_id,
    ).exclude(
        assigned_user__isnull=True,
    )

    user_results = User.objects.filter(
        #is_deleted="FALSE",
    ).exclude(
        id__in=group_permission.values_list('assigned_user_id')
    )

    # Loaed the template
    t = loader.get_template('NearBeach/opportunity/opportunity_user_permission.html')

    c = {
        'group_permission': group_permission,
        'user_results': user_results,
        'opportunity_user_permission_form': opportunity_user_permission_form(user_results=user_results),
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def organisation_information(request, organisation_id):
    permission_results = return_user_permission_level(request, None,['organisation','organisation_campus','customer'])

    if permission_results['organisation'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    # Get the data from the form if the information has been submitted
    if request.method == "POST" and permission_results['organisation'] > 1:
        form = organisation_information_form(request.POST, request.FILES)
        if form.is_valid():
            save_data = organisation.objects.get(organisation_id=organisation_id)


            # Extract it from website
            save_data.organisation_name = form.cleaned_data['organisation_name']
            save_data.organisation_website = form.cleaned_data['organisation_website']
            save_data.change_user=request.user

            # Check to see if the picture has been updated
            update_profile_picture = request.FILES.get('update_profile_picture')
            if not update_profile_picture == None:
                save_data.organisation_profile_picture = update_profile_picture

            # Save
            save_data.save()

    # Query the database for organisation information
    organisation_results = organisation.objects.get(pk=organisation_id)
    campus_results = campus.objects.filter(organisation_id=organisation_id)
    customer_results = customer.objects.filter(organisation_id=organisation_results)
    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        organisation_id=organisation_id,
    )


    project_results = project.objects.filter(organisation_id=organisation_id)
    task_results = task.objects.filter(organisation_id=organisation_id)
    #opportunity_results = opportunity.objects.filter(organisation_id=organisation_id)
    """
    We need to limit the amount of opportunities to those that the user has access to.
    """
    user_groups_results = user_group.objects.filter(username=request.user)

    opportunity_permissions_results = opportunity_permission.objects.filter(
        Q(
            Q(assigned_user=request.user)  # User has permission
            | Q(group_id__in=user_groups_results.values('group_id'))  # User's group have permission
            | Q(all_user='TRUE')  # All users have access
        )
    )
    opportunity_results = opportunity.objects.filter(
        is_deleted="FALSE",
        organisation_id=organisation_id,
        #opportunity_id__in=opportunity_permissions_results.values('opportunity_id') #There a bug with this line
    )


    # Date required to initiate date
    today = datetime.datetime.now()

    # Loaed the template
    t = loader.get_template('NearBeach/organisation_information.html')

    # profile picture


    try:
        profile_picture = organisation_results.organisation_profile_picture.url
    except:
        profile_picture = ''


    c = {
        'organisation_results': organisation_results,
        'campus_results': campus_results,
        'customer_results': customer_results,
        'organisation_information_form': organisation_information_form(
            instance=organisation_results,
            initial={
                'start_date_year': today.year,
                'start_date_month': today.month,
                'start_date_day': today.day,
            }),
        'profile_picture': profile_picture,
        'project_results': project_results,
        'task_results': task_results,
        'opportunity_results': opportunity_results,
        'PRIVATE_MEDIA_URL': settings.PRIVATE_MEDIA_URL,
        'organisation_id': organisation_id,
        'organisation_permissions': permission_results['organisation'],
        'organisation_campus_permissions': permission_results['organisation_campus'],
        'customer_permissions': permission_results['customer'],
        'quote_results':quote_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))

@login_required(login_url='login')
def permission_denied(request):
    #The user has no access to this page
    # Load the template
    t = loader.get_template('NearBeach/permission_denied.html')

    # context
    c = {
    }

    return HttpResponse(t.render(c, request))



"""
Issue - preview_quote will ask extract_quote to login. To remove this issue we have added the ability for UUID,
so the chances of a random user guessing the URL will be very small.
"""
def preview_quote(request,quote_uuid,quote_template_id):
    #Get data
    quote_results = quote.objects.get(quote_uuid=quote_uuid)
    quote_id = quote_results.quote_id

    product_results = quote_product_and_service.objects.filter(
        is_deleted="FALSE",
        #product_and_service.product_or_service = "product",
        product_and_service__in=product_and_service.objects.filter(
            product_or_service="Product",
        ).values('pk'),
        quote_id=quote_id,
    )
    service_results = quote_product_and_service.objects.filter(
        is_deleted="FALSE",
        # product_and_service.product_or_service = "product",
        product_and_service__in=product_and_service.objects.filter(
            product_or_service="Service",
        ).values('pk'),
        quote_id=quote_id,
    )

    quote_template_results = quote_template.objects.get(quote_template_id=quote_template_id)

    """
    The following section will extract the template fields and then do a simple mail merge until all the required
    template fields are JUST strings. This is the function update_template_strings
    """

    template_css = update_template_strings(quote_template_results.template_css,quote_results)
    header = update_template_strings(quote_template_results.header,quote_results)
    company_letter_head = update_template_strings(quote_template_results.company_letter_head,quote_results)
    payment_terms = update_template_strings(quote_template_results.payment_terms,quote_results)
    notes = update_template_strings(quote_template_results.notes,quote_results)
    organisation_details = update_template_strings(quote_template_results.organisation_details,quote_results)
    product_line = update_template_strings(quote_template_results.product_line,quote_results)
    service_line = update_template_strings(quote_template_results.service_line,quote_results)
    payment_method = update_template_strings(quote_template_results.payment_method,quote_results)
    footer = update_template_strings(quote_template_results.footer,quote_results)

    #Collect all the SUM information
    product_unadjusted_price=product_results.aggregate(Sum('product_price'))
    product_discount=product_results.aggregate(Sum('discount_amount'))
    product_sales_price=product_results.aggregate(Sum('sales_price'))
    product_tax=product_results.aggregate(Sum('tax'))
    product_total=product_results.aggregate(Sum('total'))

    service_unadjusted_price=service_results.aggregate(Sum('product_price'))
    service_discount=service_results.aggregate(Sum('discount_amount'))
    service_sales_price=service_results.aggregate(Sum('sales_price'))
    service_tax=service_results.aggregate(Sum('tax'))
    service_total=service_results.aggregate(Sum('total'))


    #Get Date
    current_date = datetime.datetime.now()

    # Load the template
    t = loader.get_template('NearBeach/render_templates/quote_template.html')

    # context
    c = {
        'template_css': template_css,
        'header': header,
        'company_letter_head': company_letter_head,
        'payment_terms': payment_terms,
        'notes': notes,
        'organisation_details': organisation_details,
        'product_line': product_line,
        'service_line': service_line,
        'payment_method': payment_method,
        'footer': footer,
        'product_unadjusted_price': product_unadjusted_price,
        'product_discount': product_discount,
        'product_sales_price': product_sales_price,
        'product_tax': product_tax,
        'product_total': product_total,
        'service_unadjusted_price': service_unadjusted_price,
        'service_discount': service_discount,
        'service_sales_price': service_sales_price,
        'service_tax': service_tax,
        'service_total': service_total,
        'current_user': request.user,
        'quote_id': quote_id,
        'current_date': current_date,
        'quote_results': quote_results,
        'product_results': product_results,
        'service_results': service_results,
    }

    return HttpResponse(t.render(c,request))



"""
TEMP CODE
"""
@login_required(login_url='login')
def private_document(request, document_key):
    """
    This is temp code. Hopefully I will make this function
    a lot better
    """
    PRIVATE_MEDIA_ROOT = settings.PRIVATE_MEDIA_ROOT
    #Now get the document location and return that to the user.
    document_results=document.objects.get(pk=document_key)

    path = PRIVATE_MEDIA_ROOT + '/' + document_results.document.name
    #path = '/home/luke/Downloads/gog_gods_will_be_watching_2.1.0.9.sh'

    """
    Serve private files to users with read permission.
    """
    #logger.debug('Serving {0} to {1}'.format(path, request.user))
    #if not permissions.has_read_permission(request, path):
    #    if settings.DEBUG:
    #        raise PermissionDenied
    #    else:
    #        raise Http404('File not found')
    return server.serve(request, path=path)


"""
END TEMP DOCUMENT
"""


@login_required(login_url='login')
def project_information(request, project_id):
    #First look at the user's permissions for the project's group.
    project_groups_results = project_group.objects.filter(
        is_deleted="FALSE",
        project_id=project.objects.get(project_id=project_id),
    ).values('group_id_id')

    permission_results = return_user_permission_level(request, project_groups_results,['project','project_history'])

    if permission_results['project'] == 0:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))


    """
	There are two buttons on the project information page. Both will come
	here. Both will save the data, however only one of them will resolve
	this project.
	"""
    # Get the data from the form if the information has been submitted
    if request.method == "POST" and permission_results['project'] >= 2: #Greater than edit :)
        form = project_information_form(request.POST, request.FILES)
        if form.is_valid():
            # Define the data we will edit
            project_results = project.objects.get(project_id=project_id)

            project_results.project_name = form.cleaned_data['project_name']
            project_results.project_description = form.cleaned_data['project_description']
            project_results.project_start_date = form.cleaned_data['project_start_date']
            project_results.project_end_date = form.cleaned_data['project_end_date']

            # Check to make sure the resolve button was hit
            if 'Resolve' in request.POST:
                # Well, we have to now resolve the data
                project_results.project_status = 'Resolved'

            project_results.change_user=request.user
            project_results.save()

            """
            Now we need to update any kanban board cards connected to this project.
            """
            kanban_card_results = kanban_card.objects.filter(
                is_deleted="FALSE",
                project_id=project_id
            )
            for row in kanban_card_results:
                row.kanban_card_text = "PRO" + str(project_id) + " - " + form.cleaned_data['project_name']
                row.save()
        else:
            print(form.errors)

    project_results = get_object_or_404(project, project_id=project_id)
    opportunity_results = project_opportunity.objects.filter(
        is_deleted="FALSE",
        project_id=project_id,
    )

    #If project is completed - send user to read only module
    if project_results.project_status == "Closed" or project_results.project_status == "Resolved":
        return HttpResponseRedirect(reverse('project_readonly', args={project_id}))

    # Obtain the required data
    project_history_results = project_history.objects.filter(project_id=project_id, is_deleted='FALSE')
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT DISTINCT
          document.document_key
        , document.document_description
        , document.document_url_location
        , document.document
        , document_folder.folder_id_id
        
        FROM 
          document
          LEFT JOIN
                document_permission
                ON document.document_key = document_permission.document_key_id
		LEFT JOIN
				folder
				ON folder.project_id_id = %s
		LEFT JOIN
				document_folder
				ON document_folder.folder_id_id = folder.folder_id
				AND document_folder.document_key_id = document.document_key

        
        WHERE 1=1
        
        AND document_permission.project_id_id = %s
        ORDER BY document.document_description 
        """, [project_id,project_id]
    )
    documents_results = cursor.fetchall()

    folders_results = folder.objects.filter(
        project_id=project_id,
        is_deleted='FALSE'
    ).order_by(
        'folder_description'
    )


    # Setup the initial data for the form
    initial = {
        'project_name': project_results.project_name,
        'project_description': project_results.project_description,
        'project_start_date': project_results.project_start_date,
        'project_end_date': project_results.project_end_date,
    }

    associated_task_results = task.objects.filter(
        is_deleted="FALSE",
        task_id__in=project_task.objects.filter(
            is_deleted="FALSE",
            project_id=project_id,
        ).values('task_id')
    )


    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        project_id = project_results,
    )


    # Load the template
    t = loader.get_template('NearBeach/project_information.html')

    # context
    c = {
        'project_information_form': project_information_form(initial=initial),
        'information_project_history_form': information_project_history_form(),
        'project_results': project_results,
        'associated_task_results': associated_task_results,
        'project_history_results': project_history_results,
        'documents_results': simplejson.dumps(documents_results,encoding='utf-8'),
        'folders_results': serializers.serialize('json', folders_results),
        'media_url': settings.MEDIA_URL,
        'quote_results': quote_results,
        'project_id': project_id,
        'project_permissions': permission_results['project'],
        'project_history_permissions': permission_results['project_history'],
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'opportunity_results': opportunity_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def quote_information(request, quote_id):
    permission_results = return_user_permission_level(request, None, 'quote')

    if permission_results['quote'] == 0:
        return HttpResponseRedirect(reverse(permission_denied))

    quotes_results = quote.objects.get(quote_id=quote_id)
    quote_template_results = quote_template.objects.filter(
        is_deleted="FALSE",
    )

    if request.method == "POST":
        form = quote_information_form(request.POST,quote_instance=quotes_results)
        if form.is_valid():
            #Extract the information from the forms
            quotes_results.quote_title = form.cleaned_data['quote_title']
            quotes_results.quote_terms = form.cleaned_data['quote_terms']
            quotes_results.quote_stage_id = form.cleaned_data['quote_stage_id']
            quotes_results.customer_notes = form.cleaned_data['customer_notes']
            quotes_results.quote_billing_address = form.cleaned_data['quote_billing_address']

            quotes_results.quote_valid_till = convert_to_utc(
                int(form.cleaned_data['quote_valid_till_year']),
                int(form.cleaned_data['quote_valid_till_month']),
                int(form.cleaned_data['quote_valid_till_day']),
                int(form.cleaned_data['quote_valid_till_hour']),
                int(form.cleaned_data['quote_valid_till_minute']),
                form.cleaned_data['quote_valid_till_meridiems']
            )

            #Check to see if we have to move quote to invoice
            if 'create_invoice' in request.POST:
                quotes_results.is_invoice = 'TRUE'
                quotes_results.quote_stage_id = list_of_quote_stage.objects.filter(is_invoice='TRUE').order_by('sort_order')[0]

            #Check to see if we have to revert the invoice to a quote
            if 'revert_quote' in request.POST:
                quotes_results.is_invoice = 'FALSE'
                quotes_results.quote_stage_id = list_of_quote_stage.objects.filter(is_invoice='FALSE').order_by('sort_order')[0]


            quotes_results.change_user=request.user
            quotes_results.save()

        else:
            print(form.errors)
    else:
        """
        We want to limit who can see what quote. The exception to this is for the user
        who just created the quote. (I should program in a warning stating that they
        might not be able to see the quote again unless they add themselves to the 
        permissions list.

        The user has to meet at least one of these conditions;
        1.) User has permission
        2.) User's group has permission
        3.) All users have permission
        """
        user_groups_results = user_group.objects.filter(username=request.user)

        quote_permission_results = quote_permission.objects.filter(
            Q(
                Q(assigned_user=request.user) # User has permission
                | Q(group_id__in=user_groups_results.values('group_id')) # User's group have permission
                | Q(all_user='TRUE') # All users have access
            )
            & Q(quote_id=quote_id)
        )

        if (not quote_permission_results):
            return HttpResponseRedirect(
                reverse(
                    permission_denied,
                )
            )




    #Determine if quote or invoice
    quote_or_invoice = 'Quote'
    if quotes_results.is_invoice == 'TRUE':
        quote_or_invoice = 'Invoice'

    """
    	The 24 hours to 12 hours formula.
    	00:00 means that it is 12:00 AM - change required for hour
    	01:00 means that it is 01:00 AM - no change required
    	12:00 means that it is 12:00 PM - change required for meridiem
    	13:00 means that it is 01:00 PM - change required for hour and meridiem
    	"""
    quote_valid_till_hour = quotes_results.quote_valid_till.hour
    quote_valid_till_meridiem = u'AM'
    if quote_valid_till_hour == 0:
        quote_valid_till_hour = 12
    elif quote_valid_till_hour == 12:
        quote_valid_till_meridiem = u'PM'
    elif quote_valid_till_hour > 12:
        start_hour = quote_valid_till_hour - 12
        quote_valid_till_meridiem = u'PM'

    # Setup the initial data for the form
    initial = {
        'quote_title': quotes_results.quote_title,
        'quote_terms': quotes_results.quote_terms,
        'quote_stage_id': quotes_results.quote_stage_id.quote_stage_id,
        'quote_valid_till_year': quotes_results.quote_valid_till.year,
        'quote_valid_till_month': quotes_results.quote_valid_till.month,
        'quote_valid_till_day': quotes_results.quote_valid_till.day,
        'quote_valid_till_hour': quote_valid_till_hour,
        'quote_valid_till_minute': quotes_results.quote_valid_till.minute,
        'quote_valid_till_meridiem': quote_valid_till_meridiem,
        'customer_notes': quotes_results.customer_notes,
        'quote_billing_address': quotes_results.quote_billing_address,
    }

    # Load the template
    t = loader.get_template('NearBeach/quote_information.html')


    # context
    c = {
        'quotes_results': quotes_results,
        'quote_information_form': quote_information_form(
            initial=initial,
            quote_instance=quotes_results,
        ),
        'quote_id': quote_id,
        'quote_or_invoice': quote_or_invoice,
        'timezone': settings.TIME_ZONE,
        'quote_template_results': quote_template_results,
        'quote_permission': permission_results['quote'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))




@login_required(login_url='login')
def quote_template_information(request,quote_template_id):
    permission_results = return_user_permission_level(request, None, 'template')

    if permission_results['template'] == 0:
        return HttpResponseRedirect(reverse(permission_denied))

    if request.method == "POST":
        form=quote_template_form(request.POST)
        if form.is_valid():
            quote_template_save=quote_template.objects.get(
                quote_template_id=quote_template_id,
            )
            quote_template_save.change_user=request.user
            quote_template_save.quote_template_description=form.cleaned_data['quote_template_description']
            quote_template_save.template_css=form.cleaned_data['template_css']
            quote_template_save.header= form.cleaned_data['header']
            quote_template_save.company_letter_head= form.cleaned_data['company_letter_head']
            quote_template_save.payment_terms= form.cleaned_data['payment_terms']
            quote_template_save.notes= form.cleaned_data['notes']
            quote_template_save.organisation_details= form.cleaned_data['organisation_details']
            #quote_template_save.product_line= form.cleaned_data['product_line']
            #quote_template_save.service_line= form.cleaned_data['service_line']
            quote_template_save.payment_method= form.cleaned_data['payment_method']
            quote_template_save.footer= form.cleaned_data['footer']
            quote_template_save.page_layout= form.cleaned_data['page_layout']
            quote_template_save.margin_left= form.cleaned_data['margin_left']
            quote_template_save.margin_right= form.cleaned_data['margin_right']
            quote_template_save.margin_top= form.cleaned_data['margin_top']
            quote_template_save.margin_bottom= form.cleaned_data['margin_bottom']
            quote_template_save.margin_header= form.cleaned_data['margin_header']
            quote_template_save.margin_footer= form.cleaned_data['margin_footer']

            if request.POST.get("delete_quote_template"):
                quote_template_save.is_deleted="TRUE"
                quote_template_save.save()
                return HttpResponseRedirect(reverse(search_templates))

            quote_template_save.save()

        else:
            print(form.errors)

    #Get data
    quote_template_results = quote_template.objects.get(quote_template_id=quote_template_id)

    # Load the template
    t = loader.get_template('NearBeach/quote_template_information.html')


    # context
    c = {
        'quote_template_form': quote_template_form(initial={
            'quote_template_description': quote_template_results.quote_template_description,
            'template_css': quote_template_results.template_css,
            'header': quote_template_results.header,
            'company_letter_head': quote_template_results.company_letter_head,
            'payment_terms': quote_template_results.payment_terms,
            'notes': quote_template_results.notes,
            'organisation_details': quote_template_results.organisation_details,
            'product_line': quote_template_results.product_line,
            'service_line': quote_template_results.service_line,
            'payment_method': quote_template_results.payment_method,
            'footer': quote_template_results.footer,
            'page_layout': quote_template_results.page_layout,
            'margin_left': quote_template_results.margin_left,
            'margin_right': quote_template_results.margin_right,
            'margin_top': quote_template_results.margin_top,
            'margin_bottom': quote_template_results.margin_bottom,
            'margin_header': quote_template_results.margin_header,
            'margin_footer': quote_template_results.margin_footer,
        }),
        'quote_template_id': quote_template_id,
        'quote_permission': permission_results['template'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))




@login_required(login_url='login')
def rename_document(request, document_key):
    if request.method == "POST":
        print(request)
    else:
        return HttpResponseBadRequest("This is a POST function. POST OFF!")


@login_required(login_url='login')
def resolve_project(request, project_id):
    project_update = project.objects.get(project_id=project_id)
    project_update.project_status = 'Resolved'
    project_update.change_user=request.user
    project_update.save()
    return HttpResponseRedirect(reverse('dashboard'))


@login_required(login_url='login')
def resolve_task(request, task_id):
    task_update = task.objects.get(task_id=task_id)
    task_update.task_status = 'Resolved'
    task_update.change_user=request.user
    task_update.save()
    return HttpResponseRedirect(reverse('dashboard'))


@login_required(login_url='login')
def search(request):
    permission_results = return_user_permission_level(request, None, 'project')

    # Load the template
    t = loader.get_template('NearBeach/search.html')

    """
	We will use the POST varable to help filter the results from the 
	database. The results will then appear below
	"""
    search_results = ''


    # Define if the page is loading in POST
    if request.method == "POST":
        form = search_form(request.POST)
        if form.is_valid():
            search_results = form.cleaned_data['search_for']

    """
	This is where the magic happens. I will remove all spaces and replace
	them with a wild card. This will be used to search the concatenated
	first and last name fields
	"""
    search_like = '%'

    for split_row in search_results.split(' '):
        search_like += split_row
        search_like += '%'


    """
    Due to POSTGRESQL being a bit fussy when it comes to LIKE statements,
    we have had to make a work around. If the post results come back as an
    INT, we will feed them into the results as an INT. Otherwise 0 will be fed
    in.
    """
    int_results = 0
    if not search_results == '':
        if isinstance(search_results,int):
            int_results = int(search_results)


    # Query the database for organisation
    project_results = project.objects.extra(
        where=[
            """
            project_id = %s
            OR project_name LIKE %s
            OR project_description LIKE %s
            """,
            """
            is_deleted="FALSE"
            """
        ],
        params=[
            int(int_results),
            search_like,
            search_like,
        ]
    )

    # Get list of task
    task_results = task.objects.extra(
        where=[
            """
            task_id = %s
            OR task_short_description LIKE %s
            OR task_long_description LIKE %s
            """,
            """
            is_deleted="FALSE"
            """
        ],
        params=[
            int(int_results),
            search_like,
            search_like,
        ]
    )

    opportunity_results = opportunity.objects.all()
    requirement_results = requirement.objects.all()

    # context
    c = {
        'search_form': search_form(initial={'search_for': search_results}),
        'project_results': project_results,
        'task_results': task_results,
        'opportunity_results': opportunity_results,
        'requirement_results': requirement_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def search_customer(request):
    permission_results = return_user_permission_level(request, None, 'project')

    # Load the template
    t = loader.get_template('NearBeach/search_customer.html')

    """
	We will use the POST varable to help filter the results from the 
	database. The results will then appear below
	"""
    search_customer_results = ''

    # Define if the page is loading in POST
    if request.method == "POST":
        form = search_customer_form(request.POST)
        if form.is_valid():
            search_customer_results = form.cleaned_data['search_customer']

    """
	This is where the magic happens. I will remove all spaces and replace
	them with a wild card. This will be used to search the concatenated
	first and last name fields
	"""
    search_customer_like = '%'

    for split_row in search_customer_results.split(' '):
        search_customer_like += split_row
        search_customer_like += '%'

    """
    The annotate function gives the ability to concat the first and last name.
    This gives us the ability to;
    1.) Filter on the joined field
    2.) Display it as is to the customer
    """
    customer_results = customer.objects.filter(
        is_deleted="FALSE"
    ).annotate(
        customer_full_name=Concat(
            'customer_first_name',
            Value(' '),
            'customer_last_name',
        )
    ).extra(
        where=[
            """
            customer_first_name || customer_last_name LIKE %s
            """
        ],
        params=[
            search_customer_like,
        ]
    )

    # context
    c = {
        'search_customer_form': search_customer_form(initial={'search_customer': search_customer_results}),
        'customer_results': customer_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def search_organisation(request):
    permission_results = return_user_permission_level(request, None, 'project')

    # Load the template
    t = loader.get_template('NearBeach/search_organisations.html')

    """
	We will use the following varable to help filterer our database
	results. ***WrTIE BETTER TOO TIRED TO DESCRIBE THIS!!!***
	"""
    search_organisation_results = ''

    # Define if the page is loading in POST
    if request.method == "POST":
        form = search_organisation_form(request.POST)
        if form.is_valid():
            search_organisation_results = form.cleaned_data['search_organisation']

    """
	This is where the magic happens. I will remove all spaces and replace
	them with a wild card. This will be used to search the concatenated
	first and last name fields
	"""
    search_organisation_like = '%'

    for split_row in search_organisation_results.split(' '):
        search_organisation_like += split_row
        search_organisation_like += '%'

    # Now search the organisation
    # organisations_results = organisation.objects.filter(organisation_name__contains = search_organisation_like)

    # Query the database for organisation
    cursor = connection.cursor()
    cursor.execute("""
		SELECT DISTINCT
		  organisation.organisation_id
		, organisation.organisation_name
		, organisation.organisation_website
		, organisation.organisation_email
		FROM organisation
		WHERE 1=1
		AND organisation.organisation_name LIKE %s
		""", [search_organisation_like])
    organisations_results = namedtuplefetchall(cursor)

    # context
    c = {
        'search_organisation_form': search_organisation_form(
            initial={'search_organisation': search_organisation_results}),
        'organisations_results': organisations_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def search_projects_task(request):
    # Load the template
    t = loader.get_template('NearBeach/search_projects_and_task.html')

    print("Search project and task")

    # context
    c = {


    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def search_templates(request):
    permission_results = return_user_permission_level(request, None, 'templates')
    if permission_results['templates'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))


    quote_template_results=quote_template.objects.filter(
        is_deleted="FALSE",
    )

    # Load the template
    t = loader.get_template('NearBeach/search_templates.html')

    print("Search templates")

    # context
    c = {
        'quote_template_results': quote_template_results,
        'search_template_form': search_template_form(),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def task_information(request, task_id):
    #First look at the user's permissions for the project's group.
    task_groups_results = task_group.objects.filter(
        is_deleted="FALSE",
        task_id=task.objects.get(task_id=task_id),
    ).values('group_id_id')

    permission_results = return_user_permission_level(request, task_groups_results,['task','task_history'])

    if permission_results['task'] == 0:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))

    current_user = request.user

    # Setup connection to the database and query it
    cursor = connection.cursor()

    cursor.execute("""
		SELECT COUNT(*)
		FROM
		  task_group
		, user_group
		WHERE 1=1
		AND task_group.group_id_id = user_group.group_id
		AND task_group.is_deleted = 'FALSE'
		AND user_group.is_deleted = 'FALSE'
		AND user_group.username_id = %s
		AND task_group.task_id_id = %s
	""", [current_user.id, task_id])
    has_permission = cursor.fetchall()


    """
	There are two buttons on the task information page. Both will come
	here. Both will save the data, however only one of them will resolve
	the task.
	"""
    # Define the data we will edit
    # task_results = task.objects.get(task_id = task_id)
    task_results = get_object_or_404(task, task_id=task_id)
    task_start_results = convert_extracted_time(task_results.task_start_date)
    task_end_results = convert_extracted_time(task_results.task_end_date)

    # Get the data from the form
    if request.method == "POST":
        form = task_information_form(request.POST, request.FILES)
        if form.is_valid():
            # Extract all the information from the form and save
            task_results.task_short_description = form.cleaned_data['task_short_description']
            task_results.task_long_description = form.cleaned_data['task_long_description']
            task_results.task_start_date = form.cleaned_data['task_start_date']
            task_results.task_end_date = form.cleaned_data['task_end_date']

            # Check to make sure the resolve button was hit
            if 'Resolve' in request.POST:
                # Well, we have to now resolve the data
                task_results.task_status = 'Resolved'

            task_results.save()

            """
            Now we need to update any kanban board cards connected to this project.
            """
            kanban_card_results = kanban_card.objects.filter(
                is_deleted="FALSE",
                task_id=task_id
            )
            for row in kanban_card_results:
                row.kanban_card_text = "TASK" + str(task_id) + " - " + form.cleaned_data['task_short_description']
                row.save()

            """
			If the user has submitted a new document. We only upload the document IF and ONLY IF the user
			has selected the "Submit" button on the "New Document" dialog. We do not want to accidently
			upload a document if we hit the "SAVE" button from a different location
			"""
            if 'new_document' in request.POST:
                document = request.FILES.get('document')
                document_description = request.POST.get("document_description")
                document_url_location = request.POST.get("document_url_location")

                parent_folder_id = request.POST.get("parent_folder_id")

                print(parent_folder_id)

                submit_document = document(
                    #task_id=task.objects.get(pk=task_id),
                    document=document,
                    document_description=document_description,
                    document_url_location=document_url_location,
                    change_user=request.user,
                )
                submit_document.save()

                print(parent_folder_id)

                #If the document is under a folder
                if isinstance(parent_folder_id, int):
                    submit_document_folder = document_folder(
                        document_key=submit_document,
                        change_user=request.user,
                        folder_id=int(parent_folder_id),
                    )
                    submit_document_folder.save()


                #Submit the document permissions
                submit_document_permissions = document_permission(
                    document_key=submit_document,
                    task_id=task.objects.get(pk=task_id),
                    change_user=request.user,
                )
                submit_document_permissions.save()

            """
			Fuck - someone wants to create a new folder...
			"""
            if 'new_folder' in request.POST:
                folder_description = form.cleaned_data['folder_description']
                folder_location = request.POST.get("folder_location")

                submit_folder = folder(
                    task_id=task.objects.get(pk=task_id),
                    folder_description=folder_description,
                    change_user=request.user,
                )

                try:
                    submit_folder.parent_folder_id = folder.objects.get(
                        folder_id=int(folder_location))
                    submit_folder.save()
                except:
                    submit_folder.save()


    # Obtain required data


    cursor.execute(
        """
        SELECT DISTINCT
          document.document_key
        , document.document_description
        , document.document_url_location
        , document.document
        , document_folder.folder_id_id
        
        FROM 
          document
          LEFT JOIN
                document_permission
                ON document.document_key = document_permission.document_key_id
		LEFT JOIN
				folder
				ON folder.task_id_id = %s
		LEFT JOIN
				document_folder
				ON document_folder.folder_id_id = folder.folder_id
				AND document_folder.document_key_id = document.document_key

        
        WHERE 1=1
        
        AND document_permission.task_id_id = %s
        ORDER BY document.document_description     
        """, [task_id,task_id])
    #documents_results = namedtuplefetchall(cursor)
    documents_results = cursor.fetchall()

    #print(documents_results)

    folders_results = folder.objects.filter(
        task_id=task_id,
        is_deleted='FALSE',
    ).order_by(
        'folder_description'
    )



    # Setup the initial
    initial = {
        'task_short_description': task_results.task_short_description,
        'task_long_description': task_results.task_long_description,
        'task_start_date': task_results.task_start_date,
        'task_end_date': task_results.task_end_date,
    }

    # Query the database for associated project information
    cursor = connection.cursor()
    cursor.execute("""
		SELECT 
		  project.project_id
		, project.project_name
		, project.project_end_date
		FROM project
			JOIN project_task
			ON project.project_id = project_task.project_id
			AND project_task.is_deleted = 'FALSE'
			AND project_task.task_id = %s
		""", [task_id])
    associated_project_results = namedtuplefetchall(cursor)


    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        task_id=task_results,
    )

    running_total = 0
    # Load the template
    t = loader.get_template('NearBeach/task_information.html')

    # context
    c = {
        'task_results': task_results,
        'task_information_form': task_information_form(initial=initial),
        'information_task_history_form': information_task_history_form(),
        'associated_project_results': associated_project_results,
        'documents_results': simplejson.dumps(documents_results,encoding='utf-8'),
        'folders_results': serializers.serialize('json', folders_results),
        'media_url': settings.MEDIA_URL,
        'task_id': task_id,
        'task_permissions': permission_results['task'],
        'task_history_permissions': permission_results['task_history'],
        'quote_results': quote_results,
        'task_results': task_results,
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def timeline(request):
    permission_results = return_user_permission_level(request, [],[])

    t = loader.get_template('NearBeach/timeline.html')

    # context
    c = {
        'timeline_form': timeline_form(),
        'start_date': datetime.datetime.now(),
        'end_date': datetime.datetime.now() + datetime.timedelta(days=31),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def timeline_data(request, destination):
    if request.method == "POST":
        form = timeline_form(request.POST)
        if form.is_valid():
            #Get Variables
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']

            #Get json_data
            if destination == "project":
                json_results = serializers.serialize(
                    'json',
                    project.objects.filter(
                        Q(is_deleted="FALSE") &
                        Q(
                            # Start and end date out of bounds
                            Q(
                                project_start_date__lte=start_date,
                                project_end_date__gte=end_date,
                            ) |

                            # Start date between start and end date
                            Q(
                                project_start_date__gte=start_date,
                                project_start_date__lte=end_date,
                            ) |

                            # End date betweeen start and end date
                            Q(
                                project_end_date__gte=start_date,
                                project_end_date__lte=end_date,
                            )
                        )

                        # ADD IN OTHER OPTIONS LATER
                    ),
                    fields={
                        'project_id',
                        'project_name',
                        'project_start_date',
                        'project_end_date',
                    }
                )
                print(json_results)
            else:
                json_results = serializers.serialize(
                    'json',
                    task.objects.filter(
                        is_deleted="FALSE",
                        # ADD IN OTHER OPTIONS LATER
                    ),
                    fields={
                        'task_id',
                        'task_short_description',
                        'task_start_date',
                        'task_end_date',
                    }

                )

            return HttpResponse(json_results, content_type='application/json')
        else:
            print(form.errors)

    else:
        return HttpResponseBadRequest("timeline date has to be done in post!")




@login_required(login_url='login')
def to_do_list(request, location_id, destination):
    if request.method == "POST":
        form = to_do_form(request.POST)
        if form.is_valid():
            to_do_submit = to_do(
                to_do=form.cleaned_data['to_do'],
                change_user=request.user,
            )
            if destination == "project":
                to_do_submit.project = project.objects.get(project_id=location_id)
            elif destination == "task":
                to_do_submit.task = task.objects.get(task_id=location_id)
            else:
                to_do_submit.opportunity = opportunity.objects.get(opportunity_id=location_id)
            to_do_submit.save()
        else:
            print(form.errors)

    # Get data
    if destination == 'project':
        to_do_results = to_do.objects.filter(
            is_deleted='FALSE',
            project_id=location_id,
        )
    elif destination == 'task':
        to_do_results = to_do.objects.filter(
            is_deleted='FALSE',
            task_id=location_id,
        )
    else: #Opportunity
        to_do_results = to_do.objects.filter(
            is_deleted='FALSE',
            opportunity_id=location_id,
        )


    # Load the template
    t = loader.get_template('NearBeach/to_do/to_do.html')

    # context
    c = {
        'to_do_results': to_do_results,
        'to_do_form': to_do_form(),
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def to_do_complete(request, to_do_id):
    to_do_update = to_do.objects.get(to_do_id=to_do_id)
    to_do_update.to_do_completed = True
    to_do_update.save()


    t = loader.get_template('NearBeach/blank.html')

    # context
    c = {}

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def user_want_remove(request,user_want_id):
    if request.method=="POST":
        user_want_save = user_want.objects.get(pk=user_want_id)
        user_want_save.is_deleted="TRUE"
        user_want_save.save()

        #Send back blank page
        t = loader.get_template('NearBeach/blank.html')

        c = {}

        return HttpResponse(t.render(c, request))
    else:
        return HttpResponseBadRequest("Sorry, this function can only be done in POST")



@login_required(login_url='login')
def user_want_view(request):
    if request.method=="POST":
        form = user_want_form(request.POST)
        if form.is_valid():
            user_want_submit=user_want()
            user_want_submit.change_user = request.user
            user_want_submit.want_choice = form.cleaned_data['want_choice']
            user_want_submit.want_choice_text = form.cleaned_data['want_choice_text']
            user_want_submit.want_skill = form.cleaned_data['want_skill']
            user_want_submit.save()
        else:
            print(form.errors)

    want_results = user_want.objects.filter(
        is_deleted="FALSE",
        want_choice="1" #User wants
    )

    not_want_results = user_want.objects.filter(
        is_deleted="FALSE",
        want_choice="0" #Does not want
    )

    t = loader.get_template('NearBeach/my_profile/user_want.html')

    c = {
        'user_want_form': user_want_form(),
        'want_results': want_results,
        'not_want_results': not_want_results,
    }

    return HttpResponse(t.render(c, request))




@login_required(login_url='login')
def user_weblink_remove(request,user_weblink_id):
    if request.method == "POST":
        weblink_save = user_weblink.objects.get(pk=user_weblink_id)
        weblink_save.is_deleted="TRUE"
        weblink_save.save()

        #Return blank page
        t = loader.get_template('NearBeach/blank.html')

        c = {}

        return HttpResponse(t.render(c,request))
    else:
        #Can only do this through post
        return HttpResponseBadRequest("Can only do this through post")


@login_required(login_url='login')
def user_weblink_view(request):
    if request.method == "POST":
        form = user_weblink_form(request.POST)
        if form.is_valid():
            user_weblink_submit = user_weblink(
                change_user=request.user,
                user_weblink_url=form.cleaned_data['user_weblink_url'],
                user_weblink_source=form.cleaned_data['user_weblink_source'],
            )
            user_weblink_submit.save()
        else:
            print(form.errors)

    #Data
    user_weblink_results=user_weblink.objects.filter(
        is_deleted="FALSE",
        change_user=request.user,
    )

    #Template
    t = loader.get_template('NearBeach/my_profile/user_weblink.html')

    c = {
        'user_weblink_form': user_weblink_form(),
        'user_weblink_results': user_weblink_results,
    }

    return HttpResponse(t.render(c, request))







"""
The following def are designed to help display a customer 404 and 500 pages
"""
def handler404(request):
    response = render_to_response(
        '404.html',
        {},
        context_instance=RequestContext(request)
    )
    response.status_code = 404
    return response


def handler500(request):
    response = render_to_response(
        '500.html',
        {},
        context_instance=RequestContext(request)
    )
    response.status_code = 500
    return response


def update_coordinates(campus_id):
    campus_results = campus.objects.get(pk=campus_id)

    #Set the address up
    address = campus_results.campus_address1 + " " + \
              campus_results.campus_address2 + " " + \
              campus_results.campus_address3 + " " + \
              campus_results.campus_suburb + " " + \
              campus_results.campus_region_id.region_name + " " + \
              campus_results.campus_country_id.country_name + " "
    print(address)
    address = address.replace("/", " ")  # Remove those pesky /



    #If there are no co-ordinates for this campus, get them and save them
    if hasattr(settings, 'GOOGLE_MAP_API_TOKEN'):
        print("Google Maps token exists")
        google_maps = GoogleMaps(api_key=settings.GOOGLE_MAP_API_TOKEN)
        try:
            location = google_maps.search(location=address)
            first_location = location.first()

            #Save the data
            campus_results.campus_longitude = first_location.lng
            campus_results.campus_latitude = first_location.lat
            campus_results.save()
        except:
            print("Sorry, there was an error getting the location details for this address.")

    elif hasattr(settings, 'MAPBOX_API_TOKEN'):
        #Get address ready for HTML

        address_coded = urllib.parse.quote_plus(address)

        url = "https://api.mapbox.com/geocoding/v5/mapbox.places/" + address_coded + ".json?access_token=" + settings.MAPBOX_API_TOKEN

        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
        print(data)
        try:
            campus_results.campus_longitude = data["features"][0]["center"][0]
            campus_results.campus_latitude = data["features"][0]["center"][1]
            campus_results.save()

            print(data["features"][0]["center"])
        except:
            print("No data for the address: " + address)

def update_template_strings(variable,quote_results):
    """
    The following function will replace all {{ tag }} variables in the template with the results from the quote
    results. The current variables are;

    Groups
    ~~~~~~
    1.) Quotes
    2.) Organisatiions
    3.) Quote Billing Address
    """
    variable = variable.replace('{{ customer_id }}', str(quote_results.customer_id))
    variable = variable.replace('{{ customer_notes }}', quote_results.customer_notes)
    variable = variable.replace('{{ is_invoice }}', quote_results.is_invoice)
    variable = variable.replace('{{ opportunity_id }}', str(quote_results.opportunity_id))
    variable = variable.replace('{{ organisation_id }}', str(quote_results.organisation_id))
    variable = variable.replace('{{ project_id }}', str(quote_results.project_id))
    variable = variable.replace('{{ quote_approval_status_id }}', str(quote_results.quote_approval_status_id))
    variable = variable.replace('{{ quote_billing_address }}', str(quote_results.quote_billing_address))
    variable = variable.replace('{{ quote_id }}', str(quote_results.quote_id))
    variable = variable.replace('{{ quote_stage_id }}', str(quote_results.quote_stage_id))
    variable = variable.replace('{{ quote_terms }}', quote_results.quote_terms)
    variable = variable.replace('{{ quote_title }}', quote_results.quote_title)
    variable = variable.replace('{{ quote_valid_till }}', str(quote_results.quote_valid_till))
    variable = variable.replace('{{ task_id }}', str(quote_results.task_id))

    #Group 2
    if quote_results.organisation_id:
        variable = variable.replace('{{ organisation_name }}', quote_results.organisation_id.organisation_name)
        variable = variable.replace('{{ organisation_website }}', quote_results.organisation_id.organisation_website)
        variable = variable.replace('{{ organisation_email }}', quote_results.organisation_id.organisation_email)
    else:
        variable = variable.replace('{{ organisation_name }}', '')
        variable = variable.replace('{{ organisation_website }}', '')
        variable = variable.replace('{{ organisation_email }}', '')

    #Group 3
    if quote_results.quote_billing_address:
        variable = variable.replace('{{ billing_address1 }}', quote_results.quote_billing_address.campus_address1)
        variable = variable.replace('{{ billing_address2 }}', quote_results.quote_billing_address.campus_address2)
        variable = variable.replace('{{ billing_address3 }}', quote_results.quote_billing_address.campus_address3)
        variable = variable.replace('{{ campus_id }}', str(quote_results.quote_billing_address.campus_id))
        variable = variable.replace('{{ campus_nickname }}', quote_results.quote_billing_address.campus_nickname)
        variable = variable.replace('{{ campus_phone }}', quote_results.quote_billing_address.campus_phone)
        variable = variable.replace('{{ campus_region_id }}', str(quote_results.quote_billing_address.campus_region_id))
        variable = variable.replace('{{ billing_suburb }}', quote_results.quote_billing_address.campus_suburb)
        if quote_results.quote_billing_address.campus_postcode == None:
            variable = variable.replace('{{ billing_postcode }}', '')
        else:
            variable = variable.replace('{{ billing_postcode }}', str(quote_results.quote_billing_address.campus_postcode))
        variable = variable.replace('{{ billing_region }}', str(quote_results.quote_billing_address.campus_region_id))
        variable = variable.replace('{{ billing_country }}', str(quote_results.quote_billing_address.campus_country_id))
    else:
        variable = variable.replace('{{ billing_address1 }}', '')
        variable = variable.replace('{{ billing_address2 }}', '')
        variable = variable.replace('{{ billing_address3 }}', '')
        variable = variable.replace('{{ billing_postcode }}', '')
        variable = variable.replace('{{ campus_id }}', '')
        variable = variable.replace('{{ campus_nickname }}', '')
        variable = variable.replace('{{ campus_phone }}', '')
        variable = variable.replace('{{ campus_region_id }}', '')
        variable = variable.replace('{{ billing_suburb }}', '')
        variable = variable.replace('{{ billing_region }}', '')
        variable = variable.replace('{{ billing_country }}', '')

    return variable
