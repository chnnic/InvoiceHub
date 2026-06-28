from decimal import Decimal
from datetime import date
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

class Company(models.Model):
    name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to="company_logos/",blank=True)
    country = models.CharField(max_length=2, default="ID")
    currency = models.CharField(max_length=3, default="IDR")
    npwp = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    website = models.URLField(blank=True)
    bank_details = models.TextField(blank=True)
    invoice_prefix = models.CharField(max_length=10, default="INV")
    invoice_number_digits = models.PositiveSmallIntegerField(default=5)
    next_invoice_number = models.PositiveBigIntegerField(default=1)
    allow_negative_stock = models.BooleanField(default=False)
    show_ppn = models.BooleanField(default=True)
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12)
    default_dpp_factor = models.DecimalField(max_digits=8, decimal_places=6, default=0.916667)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name
    def invoice_number_preview(self):
        return f"{self.invoice_prefix}{str(self.next_invoice_number).zfill(self.invoice_number_digits)}"

class SystemSetting(models.Model):
    allow_company_signup = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = "System setting"
        verbose_name_plural = "System settings"
    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"allow_company_signup": True})
        return obj

class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER="owner", "Owner"; ADMIN="admin", "Admin"; FINANCE="finance", "Finance"; SALES="sales", "Sales"; VIEWER="viewer", "Viewer"
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.VIEWER)
    active = models.BooleanField(default=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["user", "company"], name="unique_company_member")]

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile({self.user.username})"

class TenantModel(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    class Meta: abstract = True

class Customer(TenantModel):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    npwp = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name

class Product(TenantModel):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=60, blank=True)
    unit = models.CharField(max_length=30, default="pcs")
    price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    track_inventory = models.BooleanField(default=True)
    stock_quantity = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    low_stock_threshold = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    def __str__(self): return self.name
    @property
    def low_stock(self): return self.track_inventory and self.stock_quantity <= self.low_stock_threshold
    @property
    def stock_warning_level(self):
        if not self.track_inventory:
            return "none"
        if self.stock_quantity < 0:
            return "critical"
        if self.stock_quantity <= self.low_stock_threshold:
            return "warning"
        return "ok"
    @property
    def stock_warning_text(self):
        if not self.track_inventory:
            return ""
        if self.stock_quantity < 0:
            return _("Negative stock: please replenish immediately.")
        if self.stock_quantity <= self.low_stock_threshold:
            return _("Low stock: please replenish soon.")
        return ""

class InventoryTransaction(TenantModel):
    class Kind(models.TextChoices):
        IN="in", _("Stock in"); OUT="out", _("Stock out"); ADJUST="adjust", _("Stock adjustment")
    product = models.ForeignKey(Product,on_delete=models.PROTECT,related_name="inventory_transactions")
    kind = models.CharField(max_length=10,choices=Kind.choices)
    quantity_change = models.DecimalField(max_digits=18,decimal_places=2)
    stock_after = models.DecimalField(max_digits=18,decimal_places=2)
    note = models.CharField(max_length=250,blank=True)
    created_by = models.ForeignKey(User,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at","-id"]

class Invoice(TenantModel):
    class Status(models.TextChoices):
        DRAFT="draft", _("Draft"); SENT="sent", _("Sent"); PARTIAL="partial", _("Partial"); PAID="paid", _("Paid"); OVERDUE="overdue", _("Overdue"); VOID="void", _("Void")
    class DeliveryStatus(models.TextChoices):
        UNSHIPPED="unshipped", _("Unshipped"); SHIPPED="shipped", _("Shipped")
    number = models.CharField(max_length=40)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    issue_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    delivery_status = models.CharField(max_length=12, choices=DeliveryStatus.choices, default=DeliveryStatus.UNSHIPPED)
    inventory_applied = models.BooleanField(default=False)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12)
    dpp_factor = models.DecimalField(max_digits=8, decimal_places=6, default=0.916667)
    discount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "number"], name="unique_company_invoice_number")]
        ordering = ["-issue_date", "-id"]
    @property
    def subtotal(self): return sum((x.quantity*x.unit_price for x in self.items.all()), Decimal("0"))
    @property
    def tax(self):
        if self.company_id and not self.company.show_ppn:
            return Decimal("0")
        return max(self.subtotal-self.discount, Decimal("0"))*self.dpp_factor*self.tax_rate/Decimal("100")
    @property
    def total(self): return self.subtotal-self.discount+self.tax
    @property
    def paid(self): return self.payments.aggregate(v=Sum("amount"))["v"] or Decimal("0")
    @property
    def balance(self): return self.total-self.paid
    def recalculate_status(self, preferred_status=None):
        if preferred_status == self.Status.VOID or self.status == self.Status.VOID:
            self.status = self.Status.VOID
            return self.status
        if self.balance <= 0:
            self.status = self.Status.PAID
        elif self.paid > 0:
            self.status = self.Status.PARTIAL
        elif self.due_date < date.today():
            self.status = self.Status.OVERDUE
        elif preferred_status == self.Status.DRAFT:
            self.status = self.Status.DRAFT
        else:
            self.status = self.Status.SENT
        return self.status

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoice_items")
    description = models.CharField(max_length=250)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    @property
    def total(self): return self.quantity*self.unit_price

class Payment(TenantModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    method = models.CharField(max_length=40, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
