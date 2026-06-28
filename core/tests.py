from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from .templatetags.core_tags import money
from .models import Company, Customer, Product, Invoice, Membership, InventoryTransaction, SystemSetting, UserProfile
from .version import VERSION
from .views import _replenish_initial_rows

class TenantIsolationTests(TestCase):
    def setUp(self):
        self.a=Company.objects.create(name="A"); self.b=Company.objects.create(name="B")
        self.ua=User.objects.create_user("a",password="passpass123"); self.ub=User.objects.create_user("b",password="passpass123")
        Membership.objects.create(user=self.ua,company=self.a,role="owner"); Membership.objects.create(user=self.ub,company=self.b,role="owner")
        self.ca=Customer.objects.create(company=self.a,name="Customer A"); self.cb=Customer.objects.create(company=self.b,name="Customer B")
        Product.objects.create(company=self.a,name="A Product",price=100)
        Product.objects.create(company=self.b,name="B Secret Product",price=200)
        self.inv=Invoice.objects.create(company=self.b,customer=self.cb,number="SECRET",issue_date=date.today(),due_date=date.today(),created_by=self.ub)
    def test_customer_list_is_isolated(self):
        self.client.force_login(self.ua); response=self.client.get(reverse("customers"))
        self.assertContains(response,"Customer A"); self.assertNotContains(response,"Customer B")
    def test_invoice_detail_is_isolated(self):
        self.client.force_login(self.ua); self.assertEqual(self.client.get(reverse("invoice_detail",args=[self.inv.pk])).status_code,404)
    def test_viewer_cannot_create(self):
        m=self.ua.memberships.get(); m.role="viewer"; m.save()
        self.client.force_login(self.ua); self.assertEqual(self.client.get(reverse("invoice_create")).status_code,403)
    def test_language_switch_replaces_url_prefix(self):
        self.client.force_login(self.ua)
        response=self.client.post("/en/language/",{"language":"id","next":"/en/"})
        self.assertRedirects(response,"/id/",fetch_redirect_response=False)
        self.assertEqual(response.cookies["django_language"].value,"id")
    def test_invoice_product_suggestions_are_tenant_isolated(self):
        self.client.force_login(self.ua)
        response=self.client.get(reverse("invoice_create"))
        self.assertContains(response,"A Product")
        self.assertNotContains(response,"B Secret Product")
        self.assertContains(response,'class="product-menu"')
        self.assertContains(response,'class="product-option"')
    def test_chinese_invoice_form_labels_are_translated(self):
        self.client.force_login(self.ua)
        response=self.client.get("/zh-hans/invoices/new/")
        self.assertContains(response,"开票日期")
        self.assertContains(response,"PPN 税率")
    def test_invoice_numbers_increment_from_company_rule(self):
        self.a.invoice_prefix="ID-"; self.a.invoice_number_digits=3; self.a.next_invoice_number=7; self.a.save()
        product = Product.objects.get(company=self.a, name="A Product")
        self.client.force_login(self.ua)
        data={"customer":self.ca.pk,"issue_date":"2026-06-20","due_date":"2026-06-30","status":"draft","tax_rate":"12","dpp_factor":"0.916667","discount":"0","notes":"","items-TOTAL_FORMS":"3","items-INITIAL_FORMS":"0","items-MIN_NUM_FORMS":"0","items-MAX_NUM_FORMS":"1000","items-0-product_id":str(product.pk),"items-0-description":"Service","items-0-quantity":"1","items-0-unit_price":"100","items-0-save_as_product":"on","items-1-description":"","items-1-quantity":"1","items-1-unit_price":"","items-2-description":"","items-2-quantity":"1","items-2-unit_price":""}
        self.assertEqual(self.client.post(reverse("invoice_create"),data).status_code,302)
        self.assertEqual(self.client.post(reverse("invoice_create"),data).status_code,302)
        self.assertEqual(list(Invoice.objects.filter(company=self.a).order_by("id").values_list("number",flat=True)),["ID-007","ID-008"])
        self.assertEqual(Product.objects.filter(company=self.a,name="Service",price=100).count(),1)
        self.a.refresh_from_db(); self.assertEqual(self.a.next_invoice_number,9)
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, -2)
    def test_invoice_creation_rejects_empty_line_items(self):
        self.client.force_login(self.ua)
        data={"customer":self.ca.pk,"issue_date":"2026-06-20","due_date":"2026-06-30","status":"draft","tax_rate":"12","dpp_factor":"0.916667","discount":"0","notes":"","items-TOTAL_FORMS":"3","items-INITIAL_FORMS":"0","items-MIN_NUM_FORMS":"0","items-MAX_NUM_FORMS":"1000","items-0-description":"","items-0-quantity":"1","items-0-unit_price":"","items-1-description":"","items-1-quantity":"1","items-1-unit_price":"","items-2-description":"","items-2-quantity":"1","items-2-unit_price":""}
        response=self.client.post(reverse("invoice_create"),data)
        self.assertEqual(response.status_code,200)
        self.assertEqual(Invoice.objects.filter(company=self.a).count(),0)
        self.assertContains(response,"Add at least one invoice line item.")
    def test_only_admin_can_open_company_settings(self):
        membership=self.ua.memberships.get(); membership.role="viewer"; membership.save()
        self.client.force_login(self.ua)
        self.assertEqual(self.client.get(reverse("company_settings")).status_code,403)
    def test_money_uses_language_appropriate_thousands_separator(self):
        with translation.override("zh-hans"): self.assertEqual(money(1234567),"1,234,567")
        with translation.override("id"): self.assertEqual(money(1234567),"1.234.567")
    def test_stock_changes_create_history_and_are_isolated(self):
        product=Product.objects.get(company=self.a,name="A Product")
        self.client.force_login(self.ua)
        response=self.client.post(reverse("inventory_change",args=[product.pk]),{"kind":"in","quantity":"25","note":"Purchase"})
        self.assertEqual(response.status_code,302); product.refresh_from_db(); self.assertEqual(product.stock_quantity,25)
        response=self.client.post(reverse("inventory_change",args=[product.pk]),{"kind":"adjust","quantity":"20","note":"Count"})
        product.refresh_from_db(); self.assertEqual(product.stock_quantity,20)
        self.assertEqual(list(InventoryTransaction.objects.filter(product=product).order_by("id").values_list("quantity_change","stock_after")),[(25,25),(-5,20)])
        other=Product.objects.get(company=self.b,name="B Secret Product")
        self.assertEqual(self.client.get(reverse("inventory_detail",args=[other.pk])).status_code,404)
    def test_stock_out_cannot_make_inventory_negative(self):
        product=Product.objects.get(company=self.a,name="A Product")
        self.client.force_login(self.ua)
        response=self.client.post(reverse("inventory_change",args=[product.pk]),{"kind":"out","quantity":"1","note":""})
        self.assertEqual(response.status_code,302); product.refresh_from_db(); self.assertEqual(product.stock_quantity,-1)
    def test_overselling_allows_negative_stock_when_enabled(self):
        product=Product.objects.get(company=self.a,name="A Product")
        self.a.allow_negative_stock=True; self.a.save(update_fields=["allow_negative_stock"])
        self.client.force_login(self.ua)
        response=self.client.post(reverse("inventory_change",args=[product.pk]),{"kind":"out","quantity":"3","note":"Oversold"})
        self.assertEqual(response.status_code,302); product.refresh_from_db(); self.assertEqual(product.stock_quantity,-3)
        row=InventoryTransaction.objects.get(product=product); self.assertEqual(row.quantity_change,-3); self.assertEqual(row.stock_after,-3)
    def test_dashboard_shows_negative_stock_warning(self):
        product=Product.objects.get(company=self.a,name="A Product")
        product.stock_quantity = -2
        product.save(update_fields=["stock_quantity"])
        self.client.force_login(self.ua)
        response=self.client.get(reverse("dashboard"))
        self.assertContains(response, "Urgent replenishment")
        self.assertContains(response, "Negative stock")
    def test_inventory_alerts_page_lists_low_stock_products(self):
        product=Product.objects.get(company=self.a,name="A Product")
        product.stock_quantity = -2
        product.save(update_fields=["stock_quantity"])
        self.client.force_login(self.ua)
        response=self.client.get(reverse("inventory_alerts"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inventory alerts")
        self.assertContains(response, "A Product")
        self.assertContains(response, "Quick replenish")
        self.assertContains(response, "All alerts")
        self.assertContains(response, "Export replenishment")
    def test_inventory_alerts_can_filter_critical_only(self):
        critical = Product.objects.get(company=self.a, name="A Product")
        critical.stock_quantity = -2
        critical.save(update_fields=["stock_quantity"])
        Product.objects.create(company=self.a, name="Low Product", stock_quantity=1, low_stock_threshold=5, price=10)
        self.client.force_login(self.ua)
        response = self.client.get(reverse("inventory_alerts"), {"level": "critical"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A Product")
        self.assertNotContains(response, "Low Product")
    def test_inventory_alerts_csv_exports_rows(self):
        product=Product.objects.get(company=self.a,name="A Product")
        product.stock_quantity = -2
        product.save(update_fields=["stock_quantity"])
        self.client.force_login(self.ua)
        response=self.client.get(reverse("inventory_alerts_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertContains(response, "A Product")
    def test_inventory_replenish_csv_exports_suggested_quantities(self):
        product = Product.objects.get(company=self.a, name="A Product")
        product.stock_quantity = -2
        product.low_stock_threshold = 10
        product.save(update_fields=["stock_quantity", "low_stock_threshold"])
        self.client.force_login(self.ua)
        response = self.client.get(reverse("inventory_replenish_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertContains(response, "Suggested replenishment")
        self.assertContains(response, "22")
    def test_batch_stock_in_updates_existing_and_creates_new_product(self):
        existing=Product.objects.get(company=self.a,name="A Product")
        self.client.force_login(self.ua)
        data={"form-TOTAL_FORMS":"2","form-INITIAL_FORMS":"0","form-MIN_NUM_FORMS":"0","form-MAX_NUM_FORMS":"1000","form-0-product":str(existing.pk),"form-0-new_product_name":"","form-0-sku":"","form-0-unit":"pcs","form-0-price":"","form-0-quantity":"10","form-0-low_stock_threshold":"","form-0-note":"Existing delivery","form-1-product":"","form-1-new_product_name":"New Batch Product","form-1-sku":"NB-1","form-1-unit":"box","form-1-price":"50000","form-1-quantity":"6","form-1-low_stock_threshold":"2","form-1-note":"First delivery"}
        response=self.client.post(reverse("inventory_batch_in"),data)
        self.assertEqual(response.status_code,302); existing.refresh_from_db(); self.assertEqual(existing.stock_quantity,10)
        new=Product.objects.get(company=self.a,name="New Batch Product"); self.assertEqual(new.stock_quantity,6); self.assertEqual(new.price,50000); self.assertEqual(new.low_stock_threshold,2)
        self.assertEqual(InventoryTransaction.objects.filter(company=self.a,kind="in").count(),2)
    def test_batch_stock_in_page_mentions_new_product_creation(self):
        self.client.force_login(self.ua)
        response=self.client.get(reverse("inventory_batch_in"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This can also create new products.")
    def test_inventory_replenish_page_prefills_alert_products(self):
        product = Product.objects.get(company=self.a, name="A Product")
        product.low_stock_threshold = 10
        product.stock_quantity = -2
        product.save(update_fields=["stock_quantity", "low_stock_threshold"])
        self.client.force_login(self.ua)
        response = self.client.get(reverse("inventory_replenish"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quick replenish")
        self.assertContains(response, "A Product")
        self.assertEqual(response.context["formset"].forms[0].initial["quantity"], Decimal("22"))
    def test_replenish_initial_rows_target_safe_buffer(self):
        product = Product.objects.get(company=self.a, name="A Product")
        product.low_stock_threshold = 8
        product.stock_quantity = 3
        product.save(update_fields=["stock_quantity", "low_stock_threshold"])
        rows = _replenish_initial_rows([product])
        self.assertEqual(rows[0]["quantity"], Decimal("13"))
    def test_system_setting_default_allows_company_signup(self):
        setting = SystemSetting.get_solo()
        self.assertTrue(setting.allow_company_signup)
    def test_signup_disabled_page_when_company_signup_off(self):
        setting = SystemSetting.get_solo()
        setting.allow_company_signup = False
        setting.save()
        response = self.client.get(reverse("signup"))
        self.assertContains(response, "Company signup disabled")

    def test_superuser_forced_password_change_flow(self):
        superuser = User.objects.create_superuser("admin2", "admin2@example.com", "oldpass123")
        UserProfile.objects.create(user=superuser, must_change_password=True)
        self.client.force_login(superuser)
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("password_change_required"), fetch_redirect_response=False)

        response = self.client.post(reverse("password_change_required"), {
            "old_password": "oldpass123",
            "new_password1": "newpass12345",
            "new_password2": "newpass12345",
        })
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        superuser.refresh_from_db()
        self.assertTrue(superuser.check_password("newpass12345"))
        self.assertFalse(superuser.profile.must_change_password)

    def test_superuser_password_change_page_updates_password(self):
        superuser = User.objects.create_superuser("admin3", "admin3@example.com", "oldpass123")
        self.client.force_login(superuser)
        response = self.client.post(reverse("superuser_password"), {
            "new_password1": "newpass12345",
            "new_password2": "newpass12345",
            "require_change_on_next_login": "on",
        })
        self.assertRedirects(response, reverse("system_settings"), fetch_redirect_response=False)
        superuser.refresh_from_db()
        self.assertTrue(superuser.check_password("newpass12345"))
        self.assertTrue(superuser.profile.must_change_password)

    def test_superuser_forced_password_change_redirects_other_system_pages(self):
        superuser = User.objects.create_superuser("admin4", "admin4@example.com", "oldpass123")
        UserProfile.objects.create(user=superuser, must_change_password=True)
        self.client.force_login(superuser)
        response = self.client.get(reverse("system_settings"))
        self.assertRedirects(response, reverse("superuser_password"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("superuser_password")).status_code, 200)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 302)

    def test_version_constant_is_present(self):
        self.assertEqual(VERSION, "1.0.13")

    def test_update_container_page_shows_manual_ssh_command(self):
        superuser = User.objects.create_superuser("root5", "root5@example.com", "oldpass123")
        self.client.force_login(superuser)
        response = self.client.get(reverse("update_container"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recommended VPS command")
        self.assertContains(response, "git pull origin main")
        self.assertContains(response, "docker compose up -d --build")

    def test_system_settings_links_to_update_guide(self):
        superuser = User.objects.create_superuser("root6", "root6@example.com", "oldpass123")
        self.client.force_login(superuser)
        response = self.client.get(reverse("system_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open update guide")

    def test_superuser_can_open_user_management_without_seeing_tenant_content(self):
        superuser = User.objects.create_superuser("root", "root@example.com", "oldpass123")
        self.client.force_login(superuser)
        response = self.client.get(reverse("system_users"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User management")
        self.assertNotContains(response, "Customer A")
        self.assertNotContains(response, "B Secret Product")

    def test_superuser_can_update_user_status_and_password(self):
        superuser = User.objects.create_superuser("root2", "root2@example.com", "oldpass123")
        target = User.objects.create_user("staff1", "staff1@example.com", "passpass123")
        self.client.force_login(superuser)
        response = self.client.post(reverse("system_users"), {
            "user_id": str(target.pk),
            "username": "staff-renamed",
            "email": "new@example.com",
            "is_active": "",
            "is_staff": "on",
            "is_superuser": "",
            "new_password1": "newpass12345",
            "new_password2": "newpass12345",
            "require_change_on_next_login": "on",
        })
        self.assertRedirects(response, reverse("system_users"), fetch_redirect_response=False)
        target.refresh_from_db()
        self.assertEqual(target.username, "staff-renamed")
        self.assertEqual(target.email, "new@example.com")
        self.assertFalse(target.is_active)
        self.assertTrue(target.is_staff)
        self.assertTrue(target.check_password("newpass12345"))
        self.assertTrue(target.profile.must_change_password)

    def test_superuser_can_toggle_user_active_state(self):
        superuser = User.objects.create_superuser("root3", "root3@example.com", "oldpass123")
        target = User.objects.create_user("staff2", "staff2@example.com", "passpass123")
        self.client.force_login(superuser)
        response = self.client.post(reverse("system_users"), {
            "user_id": str(target.pk),
            "action": "toggle_active",
        })
        self.assertRedirects(response, reverse("system_users"), fetch_redirect_response=False)
        target.refresh_from_db()
        self.assertFalse(target.is_active)

    def test_superuser_can_reset_password_from_user_list(self):
        superuser = User.objects.create_superuser("root4", "root4@example.com", "oldpass123")
        target = User.objects.create_user("staff3", "staff3@example.com", "passpass123")
        self.client.force_login(superuser)
        response = self.client.post(reverse("system_users"), {
            "user_id": str(target.pk),
            "action": "reset_password",
        })
        self.assertRedirects(response, reverse("system_users"), fetch_redirect_response=False)
        target.refresh_from_db()
        self.assertTrue(target.profile.must_change_password)
        self.assertFalse(target.check_password("passpass123"))

    def test_payment_updates_invoice_status_automatically(self):
        self.client.force_login(self.ua)
        product = Product.objects.get(company=self.a, name="A Product")
        data={"customer":self.ca.pk,"issue_date":"2026-06-20","due_date":"2026-06-30","status":"draft","tax_rate":"12","dpp_factor":"0.916667","discount":"0","notes":"","items-TOTAL_FORMS":"3","items-INITIAL_FORMS":"0","items-MIN_NUM_FORMS":"0","items-MAX_NUM_FORMS":"1000","items-0-product_id":str(product.pk),"items-0-description":"Service","items-0-quantity":"1","items-0-unit_price":"100","items-1-description":"","items-1-quantity":"1","items-1-unit_price":"","items-2-description":"","items-2-quantity":"1","items-2-unit_price":""}
        self.client.post(reverse("invoice_create"),data)
        invoice=Invoice.objects.get(company=self.a)
        self.assertEqual(invoice.status,"draft")
        self.client.post(reverse("payment_add",args=[invoice.pk]),{"date":"2026-06-21","amount":"100","method":"cash","reference":"cash-1"})
        invoice.refresh_from_db()
        self.assertEqual(invoice.status,"paid")
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 0)
