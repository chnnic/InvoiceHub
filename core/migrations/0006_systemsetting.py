from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("core","0005_company_allow_negative_stock")]
    operations=[
        migrations.CreateModel(name="SystemSetting",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("allow_company_signup",models.BooleanField(default=True)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("updated_at",models.DateTimeField(auto_now=True)),
        ]),
    ]
