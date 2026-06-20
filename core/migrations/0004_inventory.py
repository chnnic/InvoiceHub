import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("core","0003_company_logo_website"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name="product",name="track_inventory",field=models.BooleanField(default=True)),
        migrations.AddField(model_name="product",name="stock_quantity",field=models.DecimalField(decimal_places=2,default=0,max_digits=18)),
        migrations.AddField(model_name="product",name="low_stock_threshold",field=models.DecimalField(decimal_places=2,default=0,max_digits=18)),
        migrations.CreateModel(name="InventoryTransaction",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("kind",models.CharField(choices=[("in","Stock in"),("out","Stock out"),("adjust","Stock adjustment")],max_length=10)),("quantity_change",models.DecimalField(decimal_places=2,max_digits=18)),("stock_after",models.DecimalField(decimal_places=2,max_digits=18)),("note",models.CharField(blank=True,max_length=250)),("created_at",models.DateTimeField(auto_now_add=True)),("company",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,to="core.company")),("created_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),("product",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="inventory_transactions",to="core.product"))],options={"ordering":["-created_at","-id"]}),
    ]
