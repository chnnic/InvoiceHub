import csv
from datetime import date
from decimal import Decimal
import os
import secrets
import shlex
import shutil
from io import StringIO
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import translation
from django.utils.translation import gettext as _
from .decorators import tenant_required, superuser_required
from .forms import SignupForm, CustomerForm, ProductForm, InvoiceForm, InvoiceItemFormSet, PaymentForm, MemberForm, CompanySettingsForm, InventoryChangeForm, BatchStockInFormSet, SystemSettingForm, AdminPasswordResetForm, FirstLoginPasswordChangeForm, SystemUserForm
from .models import Company, Customer, Product, Invoice, Payment, Membership, InventoryTransaction, SystemSetting, UserProfile

INVOICE_FILTER_STATUS = {"draft", "sent", "partial", "paid", "overdue", "void"}
INVOICE_FILTER_DELIVERY_STATUS = {"unshipped", "shipped"}

def _invoice_filter_params(request):
    quick = request.GET.get("quick", "").strip()
    status = request.GET.get("status", "").strip()
    delivery_status = request.GET.get("delivery_status", "").strip()
    customer = request.GET.get("customer", "").strip()
    month = request.GET.get("month", "").strip()
    query = request.GET.get("q", "").strip()
    if status not in INVOICE_FILTER_STATUS:
        status = ""
    if delivery_status not in INVOICE_FILTER_DELIVERY_STATUS:
        delivery_status = ""
    if quick not in {"unpaid"}:
        quick = ""
    return {
        "quick": quick,
        "status": status,
        "delivery_status": delivery_status,
        "customer": customer,
        "month": month,
        "q": query,
    }

def _filtered_invoices(company, params):
    invoices = Invoice.objects.filter(company=company).select_related("customer").prefetch_related("items", "payments")
    status = params.get("status")
    delivery_status = params.get("delivery_status")
    customer = params.get("customer")
    month = params.get("month")
    query = params.get("q")
    quick = params.get("quick")
    if status:
        invoices = invoices.filter(status=status)
    if quick == "unpaid":
        invoices = invoices.exclude(status__in=[Invoice.Status.PAID, Invoice.Status.VOID, Invoice.Status.DRAFT])
    if delivery_status:
        invoices = invoices.filter(delivery_status=delivery_status)
    if customer and customer.isdigit():
        invoices = invoices.filter(customer_id=customer)
    if month:
        try:
            year, month_num = month.split("-", 1)
            invoices = invoices.filter(issue_date__year=int(year), issue_date__month=int(month_num))
        except Exception:
            pass
    if query:
        invoices = invoices.filter(number__icontains=query)
    if quick == "unpaid":
        invoices = [invoice for invoice in invoices if invoice.balance > 0]
    return invoices

def _invoice_summary(invoices):
    totals = {}
    customer_rows = {}
    month_rows = {}
    invoice_list = list(invoices)
    for invoice in invoice_list:
        totals.setdefault(invoice.status, 0)
        totals[invoice.status] += 1
        customer_rows.setdefault(invoice.customer.name, Decimal("0"))
        customer_rows[invoice.customer.name] += invoice.total
        month_key = invoice.issue_date.strftime("%Y-%m")
        month_rows.setdefault(month_key, Decimal("0"))
        month_rows[month_key] += invoice.total
    return {
        "status_counts": totals,
        "status_rows": [(status, label, totals.get(status, 0)) for status, label in Invoice.Status.choices],
        "customer_totals": sorted(customer_rows.items(), key=lambda item: item[1], reverse=True)[:8],
        "month_totals": sorted(month_rows.items(), key=lambda item: item[0], reverse=True)[:12],
        "invoice_count": len(invoice_list),
        "invoice_total": sum((invoice.total for invoice in invoice_list), Decimal("0")),
    }

def _sync_invoice_inventory(invoice, cleaned_forms, company, user, number, previous_items=None):
    desired = {}
    save_candidates = []
    if cleaned_forms is None:
        for item in invoice.items.select_related("product").all():
            if item.product_id:
                desired[item.product_id] = desired.get(item.product_id, Decimal("0")) + item.quantity
    else:
        for item_form in cleaned_forms:
            data = item_form.cleaned_data
            if not data or data.get("DELETE"):
                continue
            product = data.get("product") or data.get("product_id")
            quantity = data.get("quantity") or Decimal("0")
            if product and quantity:
                desired[product.pk] = desired.get(product.pk, Decimal("0")) + quantity
            if data.get("save_as_product") and data.get("description") and data.get("unit_price") is not None:
                save_candidates.append((data["description"].strip(), data["unit_price"]))

    existing = {}
    source_items = previous_items if previous_items is not None else invoice.items.select_related("product").all()
    for item in source_items:
        if item.product_id:
            existing[item.product_id] = existing.get(item.product_id, Decimal("0")) + item.quantity

    product_ids = set(existing) | set(desired)
    stock_warnings = []
    for product_id in product_ids:
        product = Product.objects.select_for_update().get(pk=product_id, company=company)
        previous = existing.get(product_id, Decimal("0"))
        current = desired.get(product_id, Decimal("0"))
        delta = current - previous
        if delta == 0:
            continue
        before = product.stock_quantity
        product.stock_quantity = before - delta
        product.save(update_fields=["stock_quantity"])
        action_note = _("Adjusted by invoice %(number)s") % {"number": number}
        if delta > 0:
            action_note = _("Issued by invoice %(number)s") % {"number": number}
        elif delta < 0:
            action_note = _("Restored by invoice %(number)s") % {"number": number}
        InventoryTransaction.objects.create(
            company=company,
            product=product,
            kind="out" if delta > 0 else "in",
            quantity_change=product.stock_quantity - before,
            stock_after=product.stock_quantity,
            note=action_note,
            created_by=user,
        )
        if product.stock_quantity < 0:
            stock_warnings.append(_("Product %(name)s is now negative. Please replenish it soon.") % {"name": product.name})

    for name, unit_price in save_candidates:
        if name and not Product.objects.filter(company=company, name__iexact=name).exists():
            Product.objects.create(company=company, name=name, price=unit_price)
    return stock_warnings

def _restore_invoice_inventory(invoice, company, user, reason, items=None):
    source_items = items if items is not None else invoice.items.select_related("product").all()
    for item in source_items:
        if not item.product_id:
            continue
        product = Product.objects.select_for_update().get(pk=item.product_id, company=company)
        before = product.stock_quantity
        product.stock_quantity = before + item.quantity
        product.save(update_fields=["stock_quantity"])
        InventoryTransaction.objects.create(
            company=company,
            product=product,
            kind="in",
            quantity_change=item.quantity,
            stock_after=product.stock_quantity,
            note=reason,
            created_by=user,
        )

def _apply_invoice_inventory_if_shipped(invoice, cleaned_forms, company, user, previous_items=None):
    if invoice.delivery_status == Invoice.DeliveryStatus.SHIPPED:
        stock_warnings = _sync_invoice_inventory(
            invoice,
            cleaned_forms,
            company,
            user,
            invoice.number,
            previous_items=previous_items if invoice.inventory_applied else [],
        )
        if not invoice.inventory_applied:
            invoice.inventory_applied = True
            invoice.save(update_fields=["inventory_applied"])
        return stock_warnings
    if invoice.inventory_applied:
        _restore_invoice_inventory(invoice, company, user, _("Shipment reversed: %(number)s") % {"number": invoice.number}, items=previous_items)
        invoice.inventory_applied = False
        invoice.save(update_fields=["inventory_applied"])
    return []

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
def invoices(request):
    params = _invoice_filter_params(request)
    invoice_qs = _filtered_invoices(request.company, params)
    invoice_list = list(invoice_qs)
    summary = _invoice_summary(invoice_list)
    querystring = request.GET.urlencode()
    can_manage_invoice = request.user.is_superuser or (getattr(request, "membership", None) and request.membership.role in {"owner", "admin", "finance"})
    return render(request, "invoices/list.html", {
        "invoices": invoice_list,
        "filters": params,
        "status_choices": Invoice.Status.choices,
        "delivery_status_choices": Invoice.DeliveryStatus.choices,
        "customers": Customer.objects.filter(company=request.company).order_by("name"),
        "summary": summary,
        "querystring": querystring,
        "can_manage_invoice": can_manage_invoice,
    })

@tenant_required()
def invoices_csv(request):
    params = _invoice_filter_params(request)
    invoices_list = list(_filtered_invoices(request.company, params))
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Number", "Customer", "Issue date", "Due date", "Status", "Delivery status", "Subtotal", "Paid", "Balance", "Total"])
    for invoice in invoices_list:
        writer.writerow([
            invoice.number,
            invoice.customer.name,
            invoice.issue_date,
            invoice.due_date,
            invoice.get_status_display(),
            invoice.get_delivery_status_display(),
            invoice.subtotal,
            invoice.paid,
            invoice.balance,
            invoice.total,
        ])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="invoices.csv"'
    return response

@tenant_required(["owner","admin","finance","sales"])
def invoice_create(request):
    form=InvoiceForm(request.POST or None,company=request.company)
    invoice=Invoice(company=request.company,created_by=request.user)
    formset=InvoiceItemFormSet(request.POST or None,instance=invoice,form_kwargs={"company":request.company})
    if request.method=="POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            company=Company.objects.select_for_update().get(pk=request.company.pk)
            number=company.invoice_number_preview()
            while Invoice.objects.filter(company=company,number=number).exists():
                company.next_invoice_number += 1; number=company.invoice_number_preview()
            invoice=form.save(commit=False)
            invoice.company=company
            invoice.created_by=request.user
            invoice.number=number
            invoice.save()
            formset.instance=invoice
            formset.save()
            stock_warnings = _apply_invoice_inventory_if_shipped(invoice, formset.forms, company, request.user, previous_items=[])
            company.next_invoice_number += 1; company.save(update_fields=["next_invoice_number"])
            invoice.recalculate_status(preferred_status=form.cleaned_data["status"])
            invoice.save(update_fields=["status"])
            for warning in stock_warnings:
                messages.warning(request, warning)
        return redirect("invoice_detail",pk=invoice.pk)
    products=Product.objects.filter(company=request.company,active=True).order_by("name")
    return render(request,"invoices/form.html",{"form":form,"formset":formset,"products":products,"next_number":request.company.invoice_number_preview(),"editing":False,"page_title":_("New invoice")})

@tenant_required(["owner","admin","finance","sales"])
def invoice_edit(request, pk):
    invoice = get_object_or_404(Invoice.objects.prefetch_related("items", "payments"), pk=pk, company=request.company)
    if invoice.status == Invoice.Status.VOID:
        messages.warning(request, _("Void invoices cannot be edited."))
        return redirect("invoice_detail", pk=pk)
    previous_items = list(invoice.items.select_related("product").all())
    form=InvoiceForm(request.POST or None, instance=invoice, company=request.company)
    formset=InvoiceItemFormSet(request.POST or None, instance=invoice, form_kwargs={"company":request.company})
    if request.method=="POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            company=Company.objects.select_for_update().get(pk=request.company.pk)
            invoice=Invoice.objects.select_for_update().get(pk=pk, company=request.company)
            previous_items = list(invoice.items.select_related("product").all())
            saved=form.save(commit=False)
            saved.company=company
            saved.created_by=invoice.created_by
            saved.number=invoice.number
            saved.save()
            requested_status = form.cleaned_data["status"]
            if requested_status == Invoice.Status.VOID:
                if invoice.inventory_applied:
                    _restore_invoice_inventory(saved, company, request.user, _("Invoice voided: %(number)s") % {"number": saved.number}, items=previous_items)
                saved.status = Invoice.Status.VOID
                saved.inventory_applied = False
                saved.delivery_status = Invoice.DeliveryStatus.UNSHIPPED
                saved.save(update_fields=["status", "inventory_applied", "delivery_status"])
                messages.success(request, _("Invoice voided."))
            else:
                formset.instance=saved
                formset.save()
                saved.inventory_applied = invoice.inventory_applied
                stock_warnings = _apply_invoice_inventory_if_shipped(saved, formset.forms, company, request.user, previous_items=previous_items)
                saved.recalculate_status(preferred_status=requested_status)
                saved.save(update_fields=["status"])
                for warning in stock_warnings:
                    messages.warning(request, warning)
            messages.success(request, _("Invoice updated."))
        return redirect("invoice_detail", pk=pk)
    products=Product.objects.filter(company=request.company,active=True).order_by("name")
    return render(request,"invoices/form.html",{"form":form,"formset":formset,"products":products,"invoice":invoice,"editing":True,"page_title":_("Edit invoice")})
@tenant_required()
def invoice_detail(request,pk):
    invoice=get_object_or_404(Invoice.objects.prefetch_related("items","payments"),pk=pk,company=request.company)
    can_manage_invoice = request.user.is_superuser or (getattr(request, "membership", None) and request.membership.role in {"owner", "admin", "finance"})
    return render(request,"invoices/detail.html",{"invoice":invoice,"payment_form":PaymentForm(),"can_manage_invoice": can_manage_invoice,"status_choices": Invoice.Status.choices,"delivery_status_choices": Invoice.DeliveryStatus.choices})
@tenant_required(["owner","admin","finance"])
def payment_add(request,pk):
    invoice=get_object_or_404(Invoice,pk=pk,company=request.company); form=PaymentForm(request.POST)
    if form.is_valid():
        if invoice.status == Invoice.Status.VOID:
            messages.warning(request, _("Void invoices cannot receive payments."))
            return redirect("invoice_detail", pk=pk)
        p=form.save(commit=False); p.company=request.company; p.invoice=invoice; p.save()
        invoice.recalculate_status(preferred_status=invoice.status)
        invoice.save(update_fields=["status"])
    return redirect("invoice_detail",pk=pk)

@tenant_required(["owner","admin","finance"])
def invoice_status_update(request, pk):
    fallback_url = reverse("invoice_detail", args=[pk])
    next_url = request.POST.get("next") or fallback_url
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = fallback_url
    if request.method != "POST":
        return redirect(fallback_url)
    requested_status = request.POST.get("status", "")
    requested_delivery_status = request.POST.get("delivery_status", "")
    valid_statuses = {value for value, _ in Invoice.Status.choices}
    valid_delivery_statuses = {value for value, _ in Invoice.DeliveryStatus.choices}
    if requested_status and requested_status not in valid_statuses:
        messages.warning(request, _("Invalid invoice status."))
        return redirect(next_url)
    if requested_delivery_status and requested_delivery_status not in valid_delivery_statuses:
        messages.warning(request, _("Invalid delivery status."))
        return redirect(next_url)
    with transaction.atomic():
        invoice = get_object_or_404(Invoice.objects.select_for_update().prefetch_related("items", "payments"), pk=pk, company=request.company)
        changed = False
        if requested_delivery_status and invoice.delivery_status != requested_delivery_status:
            previous_delivery_status = invoice.delivery_status
            invoice.delivery_status = requested_delivery_status
            invoice.save(update_fields=["delivery_status"])
            if requested_delivery_status == Invoice.DeliveryStatus.SHIPPED and not invoice.inventory_applied:
                stock_warnings = _sync_invoice_inventory(invoice, None, request.company, request.user, invoice.number, previous_items=[])
                invoice.inventory_applied = True
                invoice.save(update_fields=["inventory_applied"])
                for warning in stock_warnings:
                    messages.warning(request, warning)
            elif previous_delivery_status == Invoice.DeliveryStatus.SHIPPED and invoice.inventory_applied:
                _restore_invoice_inventory(invoice, request.company, request.user, _("Shipment reversed: %(number)s") % {"number": invoice.number})
                invoice.inventory_applied = False
                invoice.save(update_fields=["inventory_applied"])
            messages.success(request, _("Delivery status updated."))
            changed = True
        if not requested_status:
            return redirect(next_url)
        if invoice.status == requested_status:
            return redirect(next_url)
        if requested_status == Invoice.Status.VOID:
            if invoice.status != Invoice.Status.VOID:
                if invoice.inventory_applied:
                    _restore_invoice_inventory(invoice, request.company, request.user, _("Invoice voided: %(number)s") % {"number": invoice.number})
            invoice.status = Invoice.Status.VOID
            invoice.delivery_status = Invoice.DeliveryStatus.UNSHIPPED
            invoice.inventory_applied = False
            invoice.save(update_fields=["status", "delivery_status", "inventory_applied"])
            messages.success(request, _("Invoice voided."))
            changed = True
        elif invoice.status == Invoice.Status.VOID:
            messages.warning(request, _("Void invoices cannot be changed to another status."))
        else:
            invoice.status = requested_status
            invoice.save(update_fields=["status"])
            messages.success(request, _("Invoice status updated."))
            changed = True
        if not changed:
            messages.info(request, _("No status changes were made."))
    return redirect(next_url)
@tenant_required(["owner","admin","finance"])
def invoice_void(request, pk):
    if request.method != "POST":
        return redirect("invoice_detail", pk=pk)
    with transaction.atomic():
        invoice = get_object_or_404(Invoice.objects.select_for_update().prefetch_related("items", "payments"), pk=pk, company=request.company)
        if invoice.status != Invoice.Status.VOID and invoice.inventory_applied:
            _restore_invoice_inventory(invoice, request.company, request.user, _("Invoice voided: %(number)s") % {"number": invoice.number})
        invoice.status = Invoice.Status.VOID
        invoice.delivery_status = Invoice.DeliveryStatus.UNSHIPPED
        invoice.inventory_applied = False
        invoice.save(update_fields=["status", "delivery_status", "inventory_applied"])
    messages.success(request, _("Invoice voided."))
    return redirect("invoice_detail", pk=pk)

@tenant_required(["owner","admin","finance"])
def invoice_delete(request, pk):
    if request.method != "POST":
        return redirect("invoice_detail", pk=pk)
    with transaction.atomic():
        invoice = get_object_or_404(Invoice.objects.select_for_update().prefetch_related("items", "payments"), pk=pk, company=request.company)
        if invoice.status != Invoice.Status.VOID and invoice.inventory_applied:
            _restore_invoice_inventory(invoice, request.company, request.user, _("Invoice deleted: %(number)s") % {"number": invoice.number})
        invoice.delete()
    messages.success(request, _("Invoice deleted."))
    return redirect("invoices")
@tenant_required()
def invoice_pdf(request,pk):
    invoice=get_object_or_404(Invoice.objects.prefetch_related("items","payments"),pk=pk,company=request.company)
    return render(request, "invoices/print.html", {"invoice": invoice, "company": request.company})

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

def _install_dir_hint():
    value = (os.environ.get("INSTALL_DIR") or "~/invoicehub").strip()
    return value or "~/invoicehub"

def _manual_update_command():
    install_dir = _install_dir_hint()
    quoted_dir = shlex.quote(install_dir)
    return "\n".join([
        f"cd {quoted_dir}",
        "git pull origin main",
        "if docker compose version >/dev/null 2>&1; then",
        "  docker compose up -d --build",
        "else",
        "  docker-compose up -d --build",
        "fi",
    ])

def _self_update_status():
    if not shutil.which("docker"):
        return False, _("Docker CLI is not available in the web container.")
    if not os.path.exists("/var/run/docker.sock"):
        return False, _("The host Docker socket is not mounted into InvoiceHub, so web updates cannot rebuild the VPS containers.")
    try:
        import subprocess

        result = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True, ""
    except Exception:
        pass
    if shutil.which("docker-compose"):
        return True, ""
    return False, _("Docker Compose is not available in the web container.")

@superuser_required
def update_container(request):
    self_update_supported, self_update_reason = _self_update_status()
    context = {
        "updated": False,
        "self_update_supported": self_update_supported,
        "self_update_reason": self_update_reason,
        "manual_update_command": _manual_update_command(),
        "install_dir_hint": _install_dir_hint(),
        "attempted": False,
    }
    if request.method == "POST":
        context["attempted"] = True
        if not self_update_supported:
            context["manual_required"] = True
            return render(request, "update_container.html", context)
        from pathlib import Path
        import subprocess
        script = Path(__file__).resolve().parent.parent / "scripts" / "update_from_github.sh"
        result = subprocess.run(["bash", str(script)], cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True, timeout=900)
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        compose_missing = "Docker Compose is required" in stderr
        already_up_to_date = "Already up to date." in stdout
        context.update({
            "updated": result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "script": str(script),
            "compose_missing": compose_missing,
            "already_up_to_date": already_up_to_date,
        })
        return render(request, "update_container.html", context)
    return render(request, "update_container.html", context)

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

def _batch_stock_in_rows(request, formset):
    with transaction.atomic():
        for row in formset.cleaned_data:
            if not row or row.get("DELETE"):
                continue
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

def _replenish_initial_rows(products):
    rows = []
    for product in products:
        suggested = (product.low_stock_threshold * 2) - product.stock_quantity
        if suggested <= 0:
            suggested = Decimal("1")
        rows.append({
            "product": product,
            "unit": product.unit,
            "price": product.price,
            "low_stock_threshold": product.low_stock_threshold,
            "quantity": suggested,
            "note": _("Replenishment"),
        })
    return rows

def _inventory_alert_products(company, level="all"):
    products = Product.objects.filter(
        company=company,
        active=True,
        track_inventory=True,
        stock_quantity__lte=F("low_stock_threshold"),
    ).order_by("stock_quantity", "name")
    if level == "critical":
        return products.filter(stock_quantity__lt=0)
    if level == "warning":
        return products.filter(stock_quantity__gte=0)
    return products

def _inventory_alert_summary(company):
    base = Product.objects.filter(
        company=company,
        active=True,
        track_inventory=True,
        stock_quantity__lte=F("low_stock_threshold"),
    )
    return {
        "all": base.count(),
        "critical": base.filter(stock_quantity__lt=0).count(),
        "warning": base.filter(stock_quantity__gte=0).count(),
    }

@tenant_required()
def inventory_alerts(request):
    level = request.GET.get("level", "all")
    if level not in {"all", "critical", "warning"}:
        level = "all"
    products = _inventory_alert_products(request.company, level)
    counts = _inventory_alert_summary(request.company)
    return render(request, "inventory/alerts.html", {
        "products": products,
        "warning_count": counts["all"],
        "critical_count": counts["critical"],
        "normal_warning_count": counts["warning"],
        "active_level": level,
    })

@tenant_required()
def inventory_alerts_csv(request):
    import csv
    from io import StringIO
    level = request.GET.get("level", "all")
    if level not in {"all", "critical", "warning"}:
        level = "all"
    products = _inventory_alert_products(request.company, level)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Product", "Current stock", "Alert threshold", "Unit", "Status"])
    for product in products:
        writer.writerow([
            product.name,
            product.stock_quantity,
            product.low_stock_threshold,
            product.unit,
            "Negative stock" if product.stock_warning_level == "critical" else "Low stock",
        ])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="inventory-alerts.csv"'
    return response

@tenant_required()
def inventory_replenish_csv(request):
    import csv
    from io import StringIO
    level = request.GET.get("level", "all")
    if level not in {"all", "critical", "warning"}:
        level = "all"
    products = _inventory_alert_products(request.company, level)
    initial_rows = _replenish_initial_rows(products)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Product", "Current stock", "Alert threshold", "Suggested replenishment", "Target stock", "Unit"])
    for row in initial_rows:
        product = row["product"]
        writer.writerow([
            product.name,
            product.stock_quantity,
            product.low_stock_threshold,
            row["quantity"],
            product.stock_quantity + row["quantity"],
            product.unit,
        ])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="inventory-replenish.csv"'
    return response

@tenant_required(["owner","admin","finance"])
def inventory_replenish(request):
    level = request.GET.get("level", "all")
    if level not in {"all", "critical", "warning"}:
        level = "all"
    products = _inventory_alert_products(request.company, level)
    formset = BatchStockInFormSet(
        request.POST or None,
        form_kwargs={"company": request.company},
        initial=_replenish_initial_rows(products),
    )
    if request.method == "POST" and formset.is_valid():
        _batch_stock_in_rows(request, formset)
        messages.success(request, _("Replenishment saved."))
        return redirect("inventory_alerts")
    return render(request, "inventory/batch_in.html", {
        "formset": formset,
        "page_title": _("Quick replenish"),
        "page_intro": _("Low-stock products are prefilled to reach a safer stock buffer. Adjust the quantities, then save."),
        "submit_label": _("Save replenishment"),
        "active_level": level,
    })

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
        _batch_stock_in_rows(request, formset)
        messages.success(request, _("Batch stock in saved."))
        return redirect("inventory")
    return render(request,"inventory/batch_in.html",{"formset":formset,"page_title":_("Batch stock in"),"page_intro":_("Select an existing product or enter a new product on each row. This can also create new products."),"submit_label":_("Save batch stock in")})
