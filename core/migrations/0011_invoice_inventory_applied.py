from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_invoice_delivery_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="inventory_applied",
            field=models.BooleanField(default=False),
        ),
    ]
