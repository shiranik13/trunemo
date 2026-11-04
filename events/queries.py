from django.db.models import Q, Sum

from .models import Gift, Payment


def gift_currency_totals(method="", selected_currency=""):
    payment_filter = Q(payments__method=method) if method else Q()
    if selected_currency:
        payment_filter &= Q(payments__currency=selected_currency)
    return {
        f"total_{currency.lower()}": Sum("payments__amount", filter=Q(payments__currency=currency) & payment_filter, default=0)
        for currency in Payment.Currency.values
    }


def event_gifts(event, search="", group_id=None, method="", currency=""):
    gifts = Gift.objects.filter(group__event=event)
    if group_id is not None:
        gifts = gifts.filter(group_id=group_id)
    if method or currency:
        matching_payments = filter_payments(Payment.objects.filter(gift__group__event=event), method, currency)
        gifts = gifts.filter(pk__in=matching_payments.values("gift_id"))
    if search:
        methods = [value for value, label in Payment.Method.choices if search.casefold() in label.casefold()]
        matches = gifts.filter(
            Q(description__icontains=search)
            | Q(group__name__icontains=search)
            | Q(recipients__name__icontains=search)
            | Q(payments__covered_guests__name__icontains=search)
            | Q(payments__payer__name__icontains=search)
            | Q(payments__method__icontains=search)
            | Q(payments__method__in=methods)
        )
        gifts = gifts.filter(pk__in=matches.values("pk"))
    return gifts.select_related("group").prefetch_related("recipients").annotate(
        **gift_currency_totals(method, currency),
    ).order_by("-pk")


def filter_payments(payments, method="", currency=""):
    if method:
        payments = payments.filter(method=method)
    if currency:
        payments = payments.filter(currency=currency)
    return payments


def payment_totals(payments):
    amounts = dict(
        ((method, currency), total)
        for method, currency, total in payments.order_by().values("method", "currency").annotate(total=Sum("amount")).values_list(
            "method", "currency", "total",
        )
    )
    breakdown = [
        (label, symbol, amounts[value, currency])
        for value, label in Payment.Method.choices
        for currency, symbol in Payment.Currency.choices
        if (value, currency) in amounts
    ]
    totals = [
        (symbol, sum(amount for (_, code), amount in amounts.items() if code == currency))
        for currency, symbol in Payment.Currency.choices
        if any(code == currency for _, code in amounts)
    ]
    return totals, breakdown
