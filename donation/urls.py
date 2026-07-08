from django.urls import path

from .views import api_alerts, api_appointments, api_cases, api_donors, api_inventory, api_reset, api_state

urlpatterns = [
    path("state/", api_state, name="api-state"),
    path("donors/", api_donors, name="api-donors"),
    path("cases/", api_cases, name="api-cases"),
    path("appointments/", api_appointments, name="api-appointments"),
    path("inventory/", api_inventory, name="api-inventory"),
    path("alerts/", api_alerts, name="api-alerts"),
    path("reset/", api_reset, name="api-reset"),
]
