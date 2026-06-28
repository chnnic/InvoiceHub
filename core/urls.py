from django.contrib.auth import views as auth
from django.urls import path
from . import views

urlpatterns = [
    path("language/", views.switch_language, name="switch_language"),
    path("login/", auth.LoginView.as_view(), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("", views.dashboard, name="dashboard"),
    path("password/change-required/", views.ensure_password_change, name="password_change_required"),
    path("customers/", views.customers, name="customers"),
    path("customers/new/", views.customer_create, name="customer_create"),
    path("products/", views.products, name="products"),
    path("products/new/", views.product_create, name="product_create"),
    path("invoices/", views.invoices, name="invoices"),
    path("invoices/new/", views.invoice_create, name="invoice_create"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/payment/", views.payment_add, name="payment_add"),
    path("invoices/<int:pk>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("members/", views.members, name="members"),
    path("settings/", views.company_settings, name="company_settings"),
    path("system/", views.system_settings, name="system_settings"),
    path("system/password/", views.superuser_password, name="superuser_password"),
    path("system/update-container/", views.update_container, name="update_container"),
    path("inventory/", views.inventory, name="inventory"),
    path("inventory/<int:pk>/", views.inventory_detail, name="inventory_detail"),
    path("inventory/<int:pk>/change/", views.inventory_change, name="inventory_change"),
    path("inventory/batch-in/", views.inventory_batch_in, name="inventory_batch_in"),
]
