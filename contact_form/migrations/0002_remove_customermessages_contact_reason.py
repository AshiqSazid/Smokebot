# Generated by Django 3.2.14 on 2022-11-20 17:15

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contact_form', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customermessages',
            name='contact_reason',
        ),
    ]
