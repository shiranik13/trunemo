from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.db.models.deletion import RestrictedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from .exports import event_workbook, guest_workbook
from .forms import EventForm, GiftForm, GroupForm, GroupGuestEntries, GuestForm, PaymentForm, SignupForm, currency_choices
from .models import Event, Gift, Guest, GuestGroup, Payment
from .queries import event_gifts, filter_payments, gift_currency_totals, payment_totals


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("dashboard")
    return render(request, "events/form.html", {
        "form": form, "title": _("Create account"), "signup_form": True,
    })


def owned_event(request, event_id):
    return get_object_or_404(Event, pk=event_id, owner=request.user)


@login_required
def dashboard(request):
    events = Event.objects.filter(owner=request.user)
    event_count = events.count()
    featured_event = events.filter(last_edited_at__isnull=False).annotate(group_count=Count("groups")).order_by(
        "-last_edited_at", "-pk",
    ).first()
    gifts = Gift.objects.filter(group__event__owner=request.user)
    guest_count = Guest.objects.filter(group__event__owner=request.user).count()
    search = request.GET.get("q", "").strip()
    if search:
        events = events.filter(name__icontains=search)
    events = events.order_by("-pk")
    return render(request, "events/dashboard.html", {
        "events": events, "event_count": event_count, "search": search,
        "featured_event": featured_event, "guest_count": guest_count,
        "gift_count": gifts.count(),
        "recent_gifts": gifts.select_related("group__event").annotate(
            **gift_currency_totals(),
        ).order_by("-pk")[:4],
    })


@login_required
def event_detail(request, event_id):
    if any(key in request.GET for key in ("q", "group", "method", "currency")):
        return redirect(f"{reverse('event_actions', args=[event_id])}?{request.GET.urlencode()}")
    event = owned_event(request, event_id)
    return render(request, "events/event.html", {
        "event": event, "groups": event.groups.prefetch_related("guests"),
    })


@login_required
def event_actions(request, event_id):
    event = owned_event(request, event_id)
    groups = list(event.groups.prefetch_related("guests"))
    search, group_id, method = gift_filters(request, groups)
    currency = selected_currency(request)
    gifts = event_gifts(event, search, group_id, method, currency)
    payments = filter_payments(Payment.objects.select_related("payer"), method, currency)
    matching_payments = payments.filter(gift__in=gifts)
    results_totals, _ = payment_totals(matching_payments)
    return render(request, "events/event_actions.html", {
        "event": event, "groups": groups, "gifts": gifts.prefetch_related(Prefetch("payments", queryset=payments)), "search": search,
        "group_id": group_id, "method": method, "methods": Payment.Method.choices,
        "is_filtered": bool(search or group_id is not None or method or currency),
        "currency": currency, "currencies": currency_choices(),
        "results_totals": results_totals,
    })


def gift_filters(request, groups):
    search = request.GET.get("q", "").strip()
    group_filter = request.GET.get("group", "")
    group_id = next((group.pk for group in groups if str(group.pk) == group_filter), None)
    method = request.GET.get("method", "")
    return search, group_id, method if method in Payment.Method.values else ""


def selected_currency(request):
    currency = request.GET.get("currency", "")
    return currency if currency in Payment.Currency.values else ""


@login_required
def event_statistics(request, event_id):
    event = owned_event(request, event_id)
    currency = selected_currency(request)
    total, breakdown = payment_totals(filter_payments(Payment.objects.filter(gift__group__event=event), currency=currency))
    return render(request, "events/statistics.html", {
        "event": event, "total": total, "breakdown": breakdown,
        "currency": currency, "currencies": currency_choices(),
    })


@login_required
def gift_detail(request, event_id, gift_id):
    event = owned_event(request, event_id)
    gift = get_object_or_404(event_gifts(event), pk=gift_id)
    return render(request, "events/gift.html", {
        "event": event, "gift": gift,
        "payments": gift.payments.select_related("payer").order_by("pk"),
    })


@login_required
def export_event(request, event_id):
    event = owned_event(request, event_id)
    search, group_id, method = gift_filters(request, event.groups.all())
    currency = selected_currency(request)
    return event_workbook(event, event_gifts(event, search, group_id, method, currency), method, currency)


@login_required
def export_guests(request, event_id):
    event = owned_event(request, event_id)
    if not event.groups.exists():
        return redirect("event_detail", event_id=event.pk)
    return guest_workbook(event)


def record_event_activity(record):
    if isinstance(record, GuestGroup):
        event_id = record.event_id
    elif isinstance(record, (Guest, Gift)):
        event_id = record.group.event_id
    elif isinstance(record, Payment):
        event_id = record.gift.group.event_id
    else:
        return
    now = timezone.now()
    Event.objects.filter(pk=event_id).filter(
        Q(last_edited_at__isnull=True) | Q(last_edited_at__lt=now),
    ).update(last_edited_at=now)


def edit_record(request, instance, form_class, title, back_url, success_url=None, *, extra_context=None):
    form = form_class(request.POST if request.method == "POST" else None, instance=instance)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            changed = not instance.pk or form.has_changed()
            record = form.save()
            if changed:
                record_event_activity(record)
        return redirect(success_url(record) if success_url else back_url)
    return render(request, "events/form.html", {
        "form": form, "title": title, "back_url": back_url, **(extra_context or {}),
    })


def delete_record(request, record, back_url, success_url=None):
    error = None
    if request.method == "POST":
        try:
            with transaction.atomic():
                record_event_activity(record)
                record.delete()
        except RestrictedError:
            error = _("This record contains a payer linked to another gift. Update that payment first.")
        else:
            return redirect(success_url or back_url)
    return render(request, "events/delete.html", {
        "record": record, "back_url": back_url, "error": error,
    })


@login_required
@require_http_methods(["GET", "POST"])
def manage_event(request, event_id=None, delete=False):
    event = owned_event(request, event_id) if event_id is not None else Event(owner=request.user)
    if delete:
        return delete_record(
            request, event, reverse("event_detail", args=[event.pk]), reverse("dashboard"),
        )
    return edit_record(
        request, event, EventForm, _("Edit event") if event.pk else _("Add event"),
        reverse("event_detail", args=[event.pk]) if event.pk else reverse("dashboard"),
        lambda record: reverse("event_detail", args=[record.pk]),
    )


@login_required
@require_http_methods(["GET", "POST"])
def manage_group(request, event_id, group_id=None, delete=False):
    event = owned_event(request, event_id)
    group = get_object_or_404(event.groups, pk=group_id) if group_id is not None else GuestGroup(event=event)
    back_url = reverse("event_detail", args=[event.pk])
    if delete:
        return delete_record(request, group, back_url)
    if group.pk:
        return edit_record(request, group, GroupForm, _("Edit group"), back_url)

    data = request.POST if request.method == "POST" else None
    form = GroupForm(data, instance=group)
    guest_data = data
    skip_payments = data is not None and "save_without_payments" in data
    if skip_payments:
        guest_data = data.copy()
        for key in data:
            parts = key.split("-", 2)
            if len(parts) == 3 and parts[0] == "guests" and parts[1].isdecimal() and parts[2] != "name":
                guest_data.pop(key)
    entries = GroupGuestEntries(guest_data, prefix="guests")
    if data is not None:
        entries_valid = entries.is_valid() if "guests-TOTAL_FORMS" in data else True
        if form.is_valid() and entries_valid:
            with transaction.atomic():
                group = form.save()
                guests = {}
                payers = []
                for index, entry in enumerate(entries.cleaned_data if "guests-TOTAL_FORMS" in data else []):
                    if not entry.get("name"):
                        continue
                    guest = Guest.objects.create(group=group, name=entry["name"])
                    guests[str(index)] = guest
                    if entry["payer"]:
                        payers.append((guest, entry))
                if payers:
                    gift = Gift.objects.create(group=group)
                    gift.recipients.set(guests.values())
                    for guest, entry in payers:
                        covered = [guests[key] for key in entry["covered"]]
                        covered = covered or (list(guests.values()) if len(payers) == 1 else [guest])
                        for amount, method, currency in entry["payments"]:
                            payment = Payment.objects.create(gift=gift, payer=guest, amount=amount, method=method, currency=currency)
                            payment.covered_guests.set(covered)
                record_event_activity(group)
            return redirect(back_url)
    return render(request, "events/group_setup.html", {
        "form": form, "entries": entries, "back_url": back_url, "submitted": data is not None and not skip_payments,
    })


@login_required
@require_http_methods(["GET", "POST"])
def manage_guest(request, event_id, group_id, guest_id=None, delete=False):
    event = owned_event(request, event_id)
    group = get_object_or_404(event.groups, pk=group_id)
    guest = get_object_or_404(group.guests, pk=guest_id) if guest_id is not None else Guest(group=group)
    back_url = reverse("event_detail", args=[event.pk])
    if delete:
        return delete_record(request, guest, back_url)
    return edit_record(request, guest, GuestForm, _("Edit guest") if guest.pk else _("Add guest"), back_url)


@login_required
@require_http_methods(["GET", "POST"])
def manage_gift(request, event_id, group_id, gift_id=None, delete=False):
    event = owned_event(request, event_id)
    group = get_object_or_404(event.groups, pk=group_id)
    if gift_id is None:
        return add_gift(request, group)
    gift = get_object_or_404(group.gifts, pk=gift_id)
    if delete:
        return delete_record(
            request, gift, reverse("gift_detail", args=[event.pk, gift.pk]),
            reverse("event_detail", args=[event.pk]),
        )
    return edit_record(
        request, gift, GiftForm, _("Edit gift"),
        reverse("gift_detail", args=[event.pk, gift.pk]),
        extra_context={"gift_group": group, "editing_gift": gift},
    )


def add_gift(request, group):
    data = request.POST if request.method == "POST" else None
    gift = Gift(group=group)
    form = GiftForm(data, instance=gift)
    payment_form = PaymentForm(data, instance=Payment(gift=gift))
    if request.method == "GET":
        payment_form.fields["amount"].widget.attrs["autofocus"] = True
    if request.method == "POST":
        gift_valid = form.is_valid()
        payment_valid = payment_form.is_valid()
        if gift_valid and payment_valid:
            with transaction.atomic():
                gift = form.save()
                payment_form.instance.gift = gift
                payment_form.save()
                record_event_activity(gift)
            if request.POST.get("add_another"):
                return redirect("gift_add", event_id=group.event_id, group_id=group.pk)
            return redirect("gift_detail", event_id=group.event_id, gift_id=gift.pk)
    return render(request, "events/form.html", {
        "form": form, "payment_form": payment_form, "title": _("Add gift"),
        "gift_group": group,
        "back_url": reverse("event_detail", args=[group.event_id]),
    })


@login_required
@require_http_methods(["GET", "POST"])
def manage_payment(request, event_id, gift_id, payment_id=None, delete=False):
    event = owned_event(request, event_id)
    gift = get_object_or_404(Gift, pk=gift_id, group__event=event)
    payment = get_object_or_404(gift.payments, pk=payment_id) if payment_id is not None else Payment(gift=gift)
    back_url = reverse("gift_detail", args=[event.pk, gift.pk])
    if delete:
        return delete_record(request, payment, back_url)
    return edit_record(request, payment, PaymentForm, _("Edit payment") if payment.pk else _("Add payment"), back_url)
