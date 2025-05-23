# Generated by Django 3.2.14 on 2022-11-24 10:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0013_auto_20221124_1043'),
    ]

    operations = [
        migrations.AlterField(
            model_name='allproducts',
            name='price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                editable=False,
                max_digits=6,
                null=True),
        ),
        migrations.AlterField(
            model_name='allproducts',
            name='slug',
            field=models.SlugField(
                blank=True,
                editable=False,
                max_length=254,
                null=True,
                unique=True),
        ),
    ]
