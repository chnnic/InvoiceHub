from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("core","0001_initial")]
    operations=[
        migrations.AddField(model_name="company",name="invoice_number_digits",field=models.PositiveSmallIntegerField(default=5)),
        migrations.AddField(model_name="company",name="next_invoice_number",field=models.PositiveBigIntegerField(default=1)),
    ]
