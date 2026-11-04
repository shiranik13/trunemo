from django import forms
from django.contrib.auth.forms import UserCreationForm
from decimal import Decimal
from copy import deepcopy
from random import choice
from django.utils.translation import get_language, gettext_lazy as _
from django.utils import timezone

from .models import Event, Gift, Guest, GuestGroup, Payment


class SignupForm(UserCreationForm):
    email = forms.EmailField(label=_("Email address"), max_length=254)

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")


def currency_choices():
    language = (get_language() or "en").split("-")[0]
    preferred = {
        "he": (Payment.Currency.ILS,),
        "ru": (Payment.Currency.RUB, Payment.Currency.EUR),
    }.get(language, (Payment.Currency.USD,))
    priority = {code: index for index, code in enumerate(preferred)}
    ordered = sorted(Payment.Currency.choices, key=lambda choice: priority.get(choice[0], len(priority)))
    return [(code, f"\u2066{symbol} ({code})\u2069") for code, symbol in ordered]


class GroupIconSelect(forms.RadioSelect):
    template_name = "events/group_icon_select.html"
    option_template_name = "events/group_icon_option.html"


class EventForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["icon"].choices = [("", _("Automatic")), *Event.Icon.choices]
        language = (get_language() or "en").split("-")[0]
        python_format, calendar_format = {
            "he": ("%d/%m/%Y", "d/m/Y"),
            "ru": ("%d.%m.%Y", "d.m.Y"),
        }.get(language, ("%m/%d/%Y", "m/d/Y"))
        date_field = self.fields["event_date"]
        date_field.input_formats = [python_format, "%Y-%m-%d"]
        date_field.widget.format = python_format
        date_field.widget.attrs["data-event-calendar"] = calendar_format

    def clean_icon(self):
        return self.cleaned_data["icon"] or choice(Event.Icon.values)

    def save(self, commit=True):
        if self.instance.pk and self.has_changed():
            self.instance.last_edited_at = timezone.now()
        return super().save(commit=commit)

    class Meta:
        model = Event
        fields = ["name", "icon", "event_date", "venue", "notes"]
        labels = {"name": _("Name"), "icon": _("Event icon"), "event_date": _("Event date"), "venue": _("Venue"), "notes": _("Event notes")}
        widgets = {
            "icon": GroupIconSelect(attrs={"data-event-icons": ""}),
            "event_date": forms.DateInput(format="%Y-%m-%d", attrs={"data-event-calendar": ""}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }


class GroupForm(forms.ModelForm):
    class Meta:
        model = GuestGroup
        fields = ["name", "icon", "notes"]
        labels = {"name": _("Name"), "icon": _("Group icon"), "notes": _("Group notes")}
        widgets = {"icon": GroupIconSelect(attrs={"class": "icon-picker"}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["icon"].choices = [("", _("Automatic")), *GuestGroup.Icon.choices]

    def clean_icon(self):
        icon = self.cleaned_data["icon"]
        if icon:
            return icon
        groups = GuestGroup.objects.filter(event_id=self.instance.event_id)
        used = set(groups.values_list("icon", flat=True))
        return choice([value for value in GuestGroup.Icon.values if value not in used] or GuestGroup.Icon.values)


class GuestForm(forms.ModelForm):
    class Meta:
        model = Guest
        fields = ["name"]
        labels = {"name": _("Name")}


class GroupGuestEntry(forms.Form):
    extra_payment_limit = 7
    name = forms.CharField(label=_("Name"), max_length=150, required=False)
    payer = forms.BooleanField(label=_("Contributed money"), required=False)
    amount = forms.DecimalField(
        label=_("Amount"), required=False, min_value=Decimal("0.01"), max_digits=12, decimal_places=2,
    )
    method = forms.ChoiceField(label=_("Payment method"), choices=[("", "---------"), *Payment.Method.choices], required=False)
    currency = forms.ChoiceField(label=_("Currency"), choices=Payment.Currency.choices, required=False, widget=forms.Select(attrs={"dir": "ltr"}))
    covered = forms.MultipleChoiceField(label=_("Paid for"), widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["currency"].choices = currency_choices()
        for index in range(1, self.extra_payment_limit + 1):
            for field in ("amount", "method", "currency"):
                self.fields[f"{field}_{index}"] = deepcopy(self.fields[field])

    def extra_payments(self):
        return [(self[f"amount_{index}"], self[f"method_{index}"], self[f"currency_{index}"]) for index in range(1, self.extra_payment_limit + 1)]

    def clean(self):
        data = super().clean()
        if data.get("payer"):
            for field in ("name", "amount", "method"):
                if field in data and not data[field]:
                    self.add_error(field, _("This field is required."))
            payments = [(data.get("amount"), data.get("method"), data.get("currency") or Payment.Currency.ILS)]
            for index in range(1, self.extra_payment_limit + 1):
                amount_field = f"amount_{index}"
                method_field = f"method_{index}"
                amount, method = data.get(amount_field), data.get(method_field)
                if amount is not None or method:
                    if amount is None and amount_field in data:
                        self.add_error(amount_field, _("This field is required."))
                    if not method and method_field in data:
                        self.add_error(method_field, _("This field is required."))
                    payments.append((amount, method, data.get(f"currency_{index}") or Payment.Currency.ILS))
            data["payments"] = payments
        return data


class GroupGuestFormSet(forms.BaseFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        if self.is_bound:
            form.fields["covered"].choices = [
                (str(row), name)
                for row in range(self.total_form_count())
                if (name := self.data.get(f"{self.prefix}-{row}-name", "").strip())
            ]


GroupGuestEntries = forms.formset_factory(
    GroupGuestEntry, formset=GroupGuestFormSet, extra=3, max_num=100, validate_max=True,
)


class GiftForm(forms.ModelForm):
    class Meta:
        model = Gift
        fields = ["description"]
        labels = {"description": _("Note (optional)")}


class PayerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, guest):
        return f"{guest.name} ({guest.group.name})"


class PaymentForm(forms.ModelForm):
    payer = PayerChoiceField(queryset=Guest.objects.none(), label=_("Payer"))
    currency = forms.ChoiceField(label=_("Currency"), choices=Payment.Currency.choices, required=False, widget=forms.Select(attrs={"dir": "ltr"}))

    def clean_currency(self):
        return self.cleaned_data["currency"] or self.instance.currency

    class Meta:
        model = Payment
        fields = ["payer", "amount", "currency", "method", "covered_guests"]
        labels = {"amount": _("Amount"), "method": _("Payment method"), "covered_guests": _("Paid for")}
        widgets = {"covered_guests": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = currency_choices()
        self.fields["currency"].choices = choices
        if not self.instance.pk and "currency" not in (kwargs.get("initial") or {}):
            self.initial["currency"] = choices[0][0]
        event_id = self.instance.gift.group.event_id
        self.fields["payer"].queryset = Guest.objects.filter(
            group__event_id=event_id,
        ).select_related("group")
        self.fields["covered_guests"].queryset = self.instance.gift.group.guests.all()
