from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_invoice_inventory_applied"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="discount_type",
            field=models.CharField(
                choices=[("amount", "Fixed amount"), ("percent", "Percentage")],
                default="amount",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="discount_percent",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
    ]
