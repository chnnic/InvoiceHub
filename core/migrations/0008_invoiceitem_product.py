import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_userprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoiceitem",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invoice_items",
                to="core.product",
            ),
        ),
    ]
