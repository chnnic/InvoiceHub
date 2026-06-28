from datetime import date
from decimal import Decimal
import secrets
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
from .decorators import tenant_required, superuser_required
from .forms import SignupForm, CustomerForm, ProductForm, InvoiceForm, InvoiceItemFormSet, PaymentForm, MemberForm, CompanySettingsForm, InventoryChangeForm, BatchStockInFormSet, SystemSettingForm, AdminPasswordResetForm, FirstLoginPasswordChangeForm, SystemUserForm
from .models import Company, Customer, Product, Invoice, Payment, Membership, InventoryTransaction, SystemSetting, UserProfile
from .pdf import build_invoice_pdf

def switch_language(request):
    """Switch the URL language prefix regardless of the active locale."""
    code = request.POST.get("language", settings.LANGUAGE_CODE)
    supported = {language for language, _ in settings.LANGUAGES}
    if code not in supported:
        code = settings.LANGUAGE_CODE
    next_path = request.POST.get("next", "/")
    if not next_path.startswith("/") or next_path.startswith("//"):
        next_path = "/"
    parts = next_path.split("/")
    if len(parts) > 1 and parts[1] in supported:
        parts[1] = code
    else:
        parts.insert(1, code)
    response = redirect("/".join(parts))
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, code, path="/")
    return response

def signup(request):
    setting = SystemSetting.get_solo()
    if not setting.allow_company_signup:
        return render(request, "registration/signup_disabled.html", {"setting": setting})
    form=SignupForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            user=form.save(); company=Company.objects.create(name=form.cleaned_data["company_name"]); Membership.objects.create(user=user, company=company, role="owner")
            UserProfile.objects.get_or_create(user=user, defaults={"must_change_password": False})
        login(request,user); translation.activate(form.cleaned_data["language"]); request.session[translation.LANGUAGE_SESSION_KEY if hasattr(translation,"LANGUAGE_SESSION_KEY") else "django_language"]=form.cleaned_data["language"]
        return redirect("dashboard")
    return render(request,"registration/signup.html",{"form":form})

@tenant_required()
def dashboard(request):
    invoices=Invoice.objects.filter(company=request.company).exclude(status="void")
    paid_expr=Coalesce(Sum("payments__amount"),Decimal("0"),output_field=DecimalField())
    monthly=(Payment.objects.filter(company=request.company,date__year=date.today().year).annotate(month=TruncMonth("date")).values("month").annotate(total=Sum("amount")).order_by("month"))
    customers=(Customer.objects.filter(company=request.company).annotate(sales=Coalesce(Sum("invoices__payments__amount"),Decimal("0"),output_field=DecimalField())).order_by("-sales")[:8])
    low_stock_products=Product.objects.filter(company=request.company,track_inventory=True,stock_quantity__lte=F("low_stock_threshold"),active=True).order_by("stock_quantity","name")
    negative_stock_products=low_stock_products.filter(stock_quantity__lt=0)
    return render(request,"dashboard.html",{"invoice_count":invoices.count(),"received":Payment.objects.filter(company=request.company).aggregate(v=Sum("amount"))["v"] or 0,"outstanding":sum((i.balance for i in invoices.prefetch_related("items","payments")),Decimal("0")),"monthly":monthly,"top_customers":customers,"recent":invoices[:8],"low_stock_count":low_stock_products.count(),"low_stock_products":low_stock_products[:6],"negative_stock_products":negative_stock_products[:6]})

@tenant_required()
def ensure_password_change(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.must_change_password:
        return redirect("dashboard")
    form = FirstLoginPasswordChangeForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password"])
        return redirect("dashboard")
    return render(request, "password_change_required.html", {"form": form})

@tenant_required()
def customers(request): return render(request,"generic/list.html",{"title":"Customers / 客户 / Pelanggan","objects":Customer.objects.filter(company=request.company),"fields":["name","email","phone"],"create_url":"customer_create"})
@tenant_required(["owner","admin","finance","sales"])
def customer_create(request):
    form=CustomerForm(request.POST or None)
    if request.method=="POST" and form.is_valid(): obj=form.save(commit=False); obj.company=request.company; obj.save(); return redirect("customers")
    return render(request,"generic/form.html",{"title":"New customer / 新客户 / Pelanggan baru","form":form})
@tenant_required()
def products(request): return render(request,"generic/list.html",{"title":"Products / 产品 / Produk","objects":Product.objects.filter(company=request.company),"fields":["name","sku","price"],"create_url":"product_create"})
@tenant_required(["owner","admin","finance","sales"])
def product_create(request):
    form=ProductForm(request.POST or None)
    if request.method=="POST" and form.is_valid(): obj=form.save(commit=False); obj.company=request.company; obj.save(); return redirect("products")
    return render(request,"generic/form.html",{"title":"New product / 新产品 / Produk baru","form":form})

@tenant_required()
def invoices(request): return render(request,"invoices/list.html",{"invoices":Invoice.objects.filter(company=request.company).select_related("customer")})
@tenant_required(["owner","admin","finance","sales"])
def invoice_create(request):
    form=InvoiceForm(request.POST or None,company=request.company); invoice=Invoice(company=request.company,created_by=request.user)
    formset=InvoiceItemFormSet(request.POST or None,instance=invoice)
    if request.method=="POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            company=Company.objects.select_for_update().get(pk=request.company.pk)
            number=company.invoice_number_preview()
            while Invoice.objects.filter(company=company,number=number).exists():
                company.next_invoice_number += 1; number=company.invoice_number_preview()
            invoice=form.save(commit=False); invoice.company=company; invoice.created_by=request.user; invoice.number=number; invoice.save(); formset.instance=invoice; formset.save()
            for item_form in formset.forms:
                data=item_form.cleaned_data
                if data and not data.get("DELETE") and data.get("save_as_product") and data.get("description") and data.get("unit_price") is not None:
                    name=data["description"].strip()
                    if not Product.objects.filter(company=company,name__iexact=name).exists(): Product.objects.create(company=company,name=name,price=data["unit_price"])
            company.next_invoice_number += 1; company.save(update_fields=["next_invoice_number"])
        return redirect("invoice_detail",pk=invoice.pk)
    products=Product.objects.filter(company=request.company,active=True).order_by("name")
    return render(request,"invoices/form.html",{"form":form,"formset":formset,"products":products,"next_number":request.company.invoice_number_preview()})
@tenant_required()
def invoice_detail(request,pk):
    invoice=get_object_or_404(Invoice.objects.prefetch_related("items","payments"),pk=pk,company=request.company)
    return render(request,"invoices/detail.html",{"invoice":invoice,"payment_form":PaymentForm()})
@tenant_required(["owner","admin","finance"])
def payment_add(request,pk):
    invoice=get_object_or_404(Invoice,pk=pk,company=request.company); form=PaymentForm(request.POST)
    if form.is_valid():
        p=form.save(commit=False); p.company=request.company; p.invoice=invoice; p.save()
        invoice.recalculate_status()
        invoice.save(update_fields=["status"])
    return redirect("invoice_detail",pk=pk)
@tenant_required()
def invoice_pdf(request,pk):
    invoice=get_object_or_404(Invoice.objects.prefetch_related("items","payments"),pk=pk,company=request.company)
    return HttpResponse(build_invoice_pdf(invoice,request.company),content_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{invoice.number}.pdf"'})

@tenant_required(["owner","admin"])
def members(request):
    form=MemberForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        user=User.objects.create_user(form.cleaned_data["username"],form.cleaned_data["email"],form.cleaned_data["password"]); Membership.objects.create(user=user,company=request.company,role=form.cleaned_data["role"]); return redirect("members")
    return render(request,"members.html",{"form":form,"members":Membership.objects.filter(company=request.company).select_related("user")})

@tenant_required(["owner","admin"])
def company_settings(request):
    form=CompanySettingsForm(request.POST or None,request.FILES or None,instance=request.company)
    if request.method=="POST" and form.is_valid(): form.save(); return redirect("company_settings")
    system_setting = SystemSetting.get_solo()
    system_form = SystemSettingForm(request.POST or None, instance=system_setting)
    return render(request,"settings.html",{"form":form,"number_preview":request.company.invoice_number_preview(),"system_form":system_form,"system_setting":system_setting})

@superuser_required
def system_settings(request):
    setting = SystemSetting.get_solo()
    form = SystemSettingForm(request.POST or None, instance=setting)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("system_settings")
    return render(request, "system_settings.html", {
        "form": form,
        "user_count": User.objects.count(),
        "active_user_count": User.objects.filter(is_active=True).count(),
    })

@superuser_required
def system_users(request):
    users = (
        User.objects.annotate(company_count=Count("memberships", distinct=True))
        .prefetch_related("memberships__company")
        .order_by("username")
    )
    selected = None
    edit_form = None
    if request.method == "POST":
        action = request.POST.get("action", "edit")
        user_id = request.POST.get("user_id")
        user = get_object_or_404(User, pk=user_id)
        if action == "toggle_active":
            user.is_active = not user.is_active
            user.save(update_fields=["is_active"])
            messages.success(request, _("User status updated."))
            return redirect("system_users")
        if action == "reset_password":
            temp_password = secrets.token_urlsafe(12)
            user.set_password(temp_password)
            user.save(update_fields=["password"])
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.must_change_password = True
            profile.save(update_fields=["must_change_password"])
            messages.success(request, _("Password reset for %(user)s. Temporary password: %(password)s") % {"user": user.username, "password": temp_password})
            return redirect("system_users")
        edit_form = SystemUserForm(request.POST, instance=user)
        if edit_form.is_valid():
            obj = edit_form.save()
            p1 = edit_form.cleaned_data.get("new_password1")
            if p1:
                obj.set_password(p1)
                obj.save(update_fields=["password"])
                profile, _ = UserProfile.objects.get_or_create(user=obj)
                profile.must_change_password = edit_form.cleaned_data["require_change_on_next_login"]
                profile.save(update_fields=["must_change_password"])
            messages.success(request, _("User updated."))
            return redirect("system_users")
        selected = user
    else:
        target = request.GET.get("user")
        if target:
            selected = get_object_or_404(User, pk=target)
            edit_form = SystemUserForm(instance=selected)
    if selected and edit_form is None:
        edit_form = SystemUserForm(instance=selected)
    return render(request, "system_users.html", {
        "users": users,
        "user_count": users.count(),
        "active_user_count": users.filter(is_active=True).count(),
        "inactive_user_count": users.filter(is_active=False).count(),
        "edit_form": edit_form,
        "selected_user": selected,
    })

@superuser_required
def superuser_password(request):
    form = AdminPasswordResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        request.user.set_password(form.cleaned_data["new_password1"])
        request.user.save(update_fields=["password"])
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.must_change_password = form.cleaned_data["require_change_on_next_login"]
        profile.save(update_fields=["must_change_password"])
        return redirect("system_settings")
    return render(request, "admin_password_change.html", {"form": form})

@superuser_required
def update_container(request):
    if request.method == "POST":
        from pathlib import Path
        import subprocess
        script = Path(__file__).resolve().parent.parent / "scripts" / "update_from_github.sh"
        result = subprocess.run(["bash", str(script)], cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True, timeout=900)
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        compose_missing = "Docker Compose is required" in stderr
        already_up_to_date = "Already up to date." in stdout
        return render(request, "update_container.html", {
            "updated": result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "script": str(script),
            "compose_missing": compose_missing,
            "already_up_to_date": already_up_to_date,
        })
    return render(request, "update_container.html", {"updated": False})

@superuser_required
def ui_mockup(request):
    mock_user_count = User.objects.count()
    mock_companies = Company.objects.count()
    mock_products = Product.objects.count()
    mock_invoices = Invoice.objects.count()
    recent_titles = [
        ("Update InvoiceHub from GitHub", _("System deployment and version sync")),
        ("User management", _("Account safety and permission control")),
        ("System settings", _("Global controls, access and version info")),
    ]
    return render(request, "ui_mockup.html", {
        "mock_user_count": mock_user_count,
        "mock_companies": mock_companies,
        "mock_products": mock_products,
        "mock_invoices": mock_invoices,
        "recent_titles": recent_titles,
    })

@tenant_required()
def inventory(request):
    products=Product.objects.filter(company=request.company,active=True).order_by("name")
    return render(request,"inventory/list.html",{"products":products})

@tenant_required()
def inventory_detail(request,pk):
    product=get_object_or_404(Product,pk=pk,company=request.company)
    history=product.inventory_transactions.filter(company=request.company).select_related("created_by")
    return render(request,"inventory/detail.html",{"product":product,"history":history})

@tenant_required(["owner","admin","finance"])
def inventory_change(request,pk):
    product=get_object_or_404(Product,pk=pk,company=request.company)
    form=InventoryChangeForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            product=Product.objects.select_for_update().get(pk=pk,company=request.company)
            before=product.stock_quantity; quantity=form.cleaned_data["quantity"]; kind=form.cleaned_data["kind"]
            after=quantity if kind=="adjust" else before+quantity if kind=="in" else before-quantity
            warning_message = None
            if after < 0:
                warning_message = _("Stock is now negative. Please replenish inventory soon.")
            product.stock_quantity=after; product.save(update_fields=["stock_quantity"])
            InventoryTransaction.objects.create(company=request.company,product=product,kind=kind,quantity_change=after-before,stock_after=after,note=form.cleaned_data["note"],created_by=request.user)
            if warning_message:
                messages.warning(request, warning_message)
            return redirect("inventory_detail",pk=pk)
    return render(request,"inventory/change.html",{"product":product,"form":form})

@tenant_required(["owner","admin","finance"])
def inventory_batch_in(request):
    formset=BatchStockInFormSet(request.POST or None,form_kwargs={"company":request.company})
    if request.method=="POST" and formset.is_valid():
        with transaction.atomic():
            for row in formset.cleaned_data:
                if not row or row.get("DELETE"): continue
                product=row.get("product")
                if product:
                    product=Product.objects.select_for_update().get(pk=product.pk,company=request.company)
                else:
                    name=row["new_product_name"].strip()
                    product=Product.objects.select_for_update().filter(company=request.company,name__iexact=name).first()
                    if not product:
                        product=Product.objects.create(company=request.company,name=name,sku=row.get("sku","").strip(),unit=row.get("unit") or "pcs",price=row.get("price") or 0,low_stock_threshold=row.get("low_stock_threshold") or 0,track_inventory=True)
                product.stock_quantity += row["quantity"]; product.save(update_fields=["stock_quantity"])
                InventoryTransaction.objects.create(company=request.company,product=product,kind="in",quantity_change=row["quantity"],stock_after=product.stock_quantity,note=row.get("note") or _("Batch stock in"),created_by=request.user)
        return redirect("inventory")
    return render(request,"inventory/batch_in.html",{"formset":formset})
