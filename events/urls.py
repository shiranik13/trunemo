from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("new/", views.manage_event, name="event_add"),
    path("<int:event_id>/", views.event_detail, name="event_detail"),
    path("<int:event_id>/actions/", views.event_actions, name="event_actions"),
    path("<int:event_id>/statistics/", views.event_statistics, name="event_statistics"),
    path("<int:event_id>/edit/", views.manage_event, name="event_edit"),
    path("<int:event_id>/delete/", views.manage_event, {"delete": True}, name="event_delete"),
    path("<int:event_id>/export/", views.export_event, name="event_export"),
    path("<int:event_id>/guests/export/", views.export_guests, name="guest_export"),
    path("<int:event_id>/groups/new/", views.manage_group, name="group_add"),
    path("<int:event_id>/groups/<int:group_id>/edit/", views.manage_group, name="group_edit"),
    path("<int:event_id>/groups/<int:group_id>/delete/", views.manage_group, {"delete": True}, name="group_delete"),
    path("<int:event_id>/groups/<int:group_id>/guests/new/", views.manage_guest, name="guest_add"),
    path("<int:event_id>/groups/<int:group_id>/guests/<int:guest_id>/edit/", views.manage_guest, name="guest_edit"),
    path("<int:event_id>/groups/<int:group_id>/guests/<int:guest_id>/delete/", views.manage_guest, {"delete": True}, name="guest_delete"),
    path("<int:event_id>/groups/<int:group_id>/gifts/new/", views.manage_gift, name="gift_add"),
    path("<int:event_id>/groups/<int:group_id>/gifts/<int:gift_id>/edit/", views.manage_gift, name="gift_edit"),
    path("<int:event_id>/groups/<int:group_id>/gifts/<int:gift_id>/delete/", views.manage_gift, {"delete": True}, name="gift_delete"),
    path("<int:event_id>/gifts/<int:gift_id>/", views.gift_detail, name="gift_detail"),
    path("<int:event_id>/gifts/<int:gift_id>/payments/new/", views.manage_payment, name="payment_add"),
    path("<int:event_id>/gifts/<int:gift_id>/payments/<int:payment_id>/edit/", views.manage_payment, name="payment_edit"),
    path("<int:event_id>/gifts/<int:gift_id>/payments/<int:payment_id>/delete/", views.manage_payment, {"delete": True}, name="payment_delete"),
]
