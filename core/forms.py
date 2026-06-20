from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import inlineformset_factory, formset_factory
from django.utils.translation import gettext_lazy as _
from .models import Company, Customer, Product, Invoice, InvoiceItem, Payment, Membership, InventoryTransaction, SystemSetting

class StyledForm:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values(): field.widget.attrs.setdefault("class", "input")

class SignupForm(StyledForm, UserCreationForm):
    company_name = forms.CharField(max_length=200, label="Company / 公司 / Perusahaan")
    language = forms.ChoiceField(choices=[("zh-hans","中文"),("en","English"),("id","Bahasa Indonesia")])
    class Meta: model=User; fields=("username","email","company_name","language","password1","password2")

class CustomerForm(StyledForm, forms.ModelForm):
    class Meta: model=Customer; exclude=("company",)
class ProductForm(StyledForm, forms.ModelForm):
    class Meta:
        model=Product; fields=("name","sku","unit","price","track_inventory","low_stock_threshold","active")
        labels={"name":_("Product name"),"sku":"SKU","unit":_("Unit"),"price":_("Price"),"track_inventory":_("Track inventory"),"low_stock_threshold":_("Low-stock threshold"),"active":_("Active")}
class InvoiceForm(StyledForm, forms.ModelForm):
    class Meta:
        model=Invoice; fields=("customer","issue_date","due_date","status","tax_rate","dpp_factor","discount","notes")
        widgets={"issue_date":forms.DateInput(attrs={"type":"date"}),"due_date":forms.DateInput(attrs={"type":"date"})}
        labels={"customer":_("Customer"),"issue_date":_("Issue date"),"due_date":_("Due date"),"status":_("Status"),"tax_rate":_("PPN rate (%)"),"dpp_factor":_("DPP factor"),"discount":_("Discount"),"notes":_("Notes")}
    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset=Customer.objects.filter(company=company)
        self.fields["status"].choices=[("draft",_("Draft")),("sent",_("Sent")),("partial",_("Partial")),("paid",_("Paid")),("overdue",_("Overdue")),("void",_("Void"))]
class InvoiceItemForm(StyledForm, forms.ModelForm):
    save_as_product=forms.BooleanField(required=False,label=_("Save to product catalog"))
    class Meta:
        model=InvoiceItem; fields=("description","quantity","unit_price")
        widgets={"description":forms.TextInput(attrs={"class":"input product-combobox","autocomplete":"off"}),"quantity":forms.NumberInput(attrs={"class":"input","step":"0.01"}),"unit_price":forms.NumberInput(attrs={"class":"input unit-price","step":"0.01"})}
InvoiceItemFormSet=inlineformset_factory(Invoice, InvoiceItem, form=InvoiceItemForm, extra=3, can_delete=True)
class PaymentForm(StyledForm, forms.ModelForm):
    class Meta:
        model=Payment; fields=("date","amount","method","reference")
        widgets={"date":forms.DateInput(attrs={"type":"date"})}
class MemberForm(StyledForm, forms.Form):
    username=forms.CharField(max_length=150); email=forms.EmailField(); password=forms.CharField(widget=forms.PasswordInput); role=forms.ChoiceField(choices=Membership.Role.choices)

class CompanySettingsForm(StyledForm, forms.ModelForm):
    class Meta:
        model=Company
        fields=("logo","name","country","currency","npwp","address","email","phone","website","bank_details","invoice_prefix","invoice_number_digits","next_invoice_number","default_tax_rate","default_dpp_factor","allow_negative_stock")
        labels={"allow_negative_stock":_("Allow negative stock (overselling)")}
    def clean_invoice_number_digits(self):
        value=self.cleaned_data["invoice_number_digits"]
        if not 1 <= value <= 12: raise forms.ValidationError("Use 1–12 digits.")
        return value

class SystemSettingForm(StyledForm, forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = ("allow_company_signup",)
        labels = {"allow_company_signup": _("Allow company signup")}

class InventoryChangeForm(StyledForm, forms.Form):
    kind=forms.ChoiceField(choices=[("in",_("Stock in")),("out",_("Stock out")),("adjust",_("Set exact stock"))],label=_("Operation"))
    quantity=forms.DecimalField(max_digits=18,decimal_places=2,min_value=0,label=_("Quantity"))
    note=forms.CharField(max_length=250,required=False,label=_("Note"))

class BatchStockInForm(StyledForm, forms.Form):
    product=forms.ModelChoiceField(queryset=Product.objects.none(),required=False,label=_("Existing product"))
    new_product_name=forms.CharField(max_length=200,required=False,label=_("New product name"))
    sku=forms.CharField(max_length=60,required=False,label="SKU")
    unit=forms.CharField(max_length=30,required=False,initial="pcs",label=_("Unit"))
    price=forms.DecimalField(max_digits=18,decimal_places=2,required=False,min_value=0,label=_("Price"))
    quantity=forms.DecimalField(max_digits=18,decimal_places=2,min_value=0.01,label=_("Stock-in quantity"))
    low_stock_threshold=forms.DecimalField(max_digits=18,decimal_places=2,required=False,min_value=0,label=_("Alert threshold"))
    note=forms.CharField(max_length=250,required=False,label=_("Note"))
    def __init__(self,*args,company=None,**kwargs):
        super().__init__(*args,**kwargs); self.fields["product"].queryset=Product.objects.filter(company=company,active=True).order_by("name")
    def clean(self):
        data=super().clean()
        if data and not data.get("product") and not data.get("new_product_name"): raise forms.ValidationError(_("Choose an existing product or enter a new product name."))
        return data
BatchStockInFormSet=formset_factory(BatchStockInForm,extra=5,can_delete=True)
