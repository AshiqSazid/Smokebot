# Generated by Django 3.2.14 on 2022-10-16 21:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_auto_20221011_1444'),
    ]

    operations = [
        migrations.AddField(
            model_name='disposablevapes',
            name='sub_class',
            field=models.CharField(
                default='disposablevape',
                editable=False,
                max_length=254,
                null=True),
        ),
    ]
