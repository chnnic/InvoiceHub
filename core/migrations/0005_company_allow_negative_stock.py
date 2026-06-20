from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("core","0004_inventory")]
    operations=[migrations.AddField(model_name="company",name="allow_negative_stock",field=models.BooleanField(default=False))]
