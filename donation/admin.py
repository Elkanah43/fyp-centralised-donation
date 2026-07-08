from django.contrib import admin

from .models import Alert, Appointment, Donor, InventoryItem, RecipientCase


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = ("name", "donor_type", "blood_type", "region", "phone", "status", "created_at")
    list_filter = ("donor_type", "blood_type", "status", "region")
    search_fields = ("name", "region", "phone")


@admin.register(RecipientCase)
class RecipientCaseAdmin(admin.ModelAdmin):
    list_display = ("recipient", "need_type", "priority", "blood_type", "organ", "hospital", "region", "created_at")
    list_filter = ("need_type", "priority", "blood_type", "region")
    search_fields = ("recipient", "hospital", "region")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("donor", "date", "time", "site", "purpose", "created_at")
    list_filter = ("purpose", "date")
    search_fields = ("donor__name", "site")
    autocomplete_fields = ("donor",)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("blood_type", "units")
    ordering = ("blood_type",)


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("level", "title", "created_at")
    list_filter = ("level",)
    search_fields = ("title", "message")
