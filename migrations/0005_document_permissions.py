# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-08-17 05:53
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('NearBeach', '0004_documents'),
    ]

    operations = [
        migrations.CreateModel(
            name='document_permissions',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('change_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_permissions_change_user', to=settings.AUTH_USER_MODEL)),
                ('customer_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.customers')),
                ('document_key', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.documents')),
                ('opportunity_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.opportunity')),
                ('organisations_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.organisations')),
                ('project_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.project')),
                ('task_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.tasks')),
                ('user_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'document_permissions',
            },
        ),
    ]