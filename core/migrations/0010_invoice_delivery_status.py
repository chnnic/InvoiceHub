from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_company_show_ppn"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="delivery_status",
            field=models.CharField(
                choices=[("unshipped", "Unshipped"), ("shipped", "Shipped")],
                default="unshipped",
                max_length=12,
            ),
        ),
    ]
