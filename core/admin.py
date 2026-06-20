from django.contrib import admin
from .models import Company, Membership, Customer, Product, Invoice, InvoiceItem, Payment, InventoryTransaction
admin.site.register([Company,Membership,Customer,Product,Invoice,InvoiceItem,Payment,InventoryTransaction])
