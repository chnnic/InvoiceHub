from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_invoiceitem_product"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="show_ppn",
            field=models.BooleanField(default=True),
        ),
    ]
