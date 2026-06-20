from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("core","0002_company_invoice_numbering")]
    operations=[
        migrations.AddField(model_name="company",name="logo",field=models.ImageField(blank=True,upload_to="company_logos/")),
        migrations.AddField(model_name="company",name="website",field=models.URLField(blank=True)),
    ]
