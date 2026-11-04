from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from .models import Event, Gift, Guest, GuestGroup, Payment


class TrunemoTests(TestCase):
    def test_language_selection_persists_and_sets_page_direction(self):
        user = get_user_model().objects.create_user(username="language-test")
        self.client.force_login(user)
        dashboard = reverse("dashboard")
        for language, direction, heading in [
            ("he", "rtl", "אירועים"),
            ("ru", "ltr", "События"),
            ("en", "ltr", "Events"),
        ]:
            with self.subTest(language=language):
                response = self.client.post(reverse("set_language"), {
                    "language": language, "next": f"{dashboard}?q=example",
                }, follow=True)
                self.assertEqual(response.request["QUERY_STRING"], "q=example")
                self.assertContains(response, f'<html lang="{language}" dir="{direction}">')
                self.assertContains(response, heading)
                for name in ("English", "עברית", "Русский"):
                    self.assertContains(response, f">{name}</option>")
                self.assertContains(self.client.get(dashboard), heading)

    def test_home_mascot_matches_selected_language(self):
        for language in ("en", "he", "ru"):
            with self.subTest(language=language):
                response = self.client.get(reverse("home"), HTTP_ACCEPT_LANGUAGE=language)
                self.assertContains(response, f"mascot/home-{language}.webp", count=1 if language == "he" else 2)

    def test_dashboard_features_last_edited_event(self):
        owner = get_user_model().objects.create_user(username="dashboard-owner")
        older = Event.objects.create(name="Older", owner=owner)
        Event.objects.create(name="Newer", owner=owner)
        self.client.force_login(owner)
        dashboard = reverse("dashboard")
        response = self.client.get(dashboard)
        self.assertIsNone(response.context["featured_event"])
        self.assertContains(response, "No edit recorded yet")
        self.client.post(reverse("event_edit", args=[older.pk]), {"name": "Updated"})
        response = self.client.get(dashboard)
        self.assertEqual(response.context["featured_event"], older)
        self.assertContains(response, "<time datetime=")
        newer = Event.objects.get(name="Newer")
        self.client.post(reverse("group_add", args=[newer.pk]), {"name": "Friends"})
        self.assertEqual(self.client.get(dashboard).context["featured_event"], newer)

    def test_guest_export_contains_notes_without_payment_data(self):
        owner = get_user_model().objects.create_user(username="guest-export-owner")
        event = Event.objects.create(name="Party", owner=owner)
        group = GuestGroup.objects.create(event=event, name="Family", notes="Needs a high chair")
        guest = Guest.objects.create(group=group, name="Ari")
        gift = Gift.objects.create(group=group)
        Payment.objects.create(gift=gift, payer=guest, amount=100, method="cash")
        self.client.force_login(owner)
        response = self.client.get(reverse("guest_export", args=[event.pk]), HTTP_ACCEPT_LANGUAGE="he")
        workbook = load_workbook(BytesIO(b"".join(response.streaming_content)))
        self.assertEqual(workbook.sheetnames, ["רשימת אורחים", "סיכום אירוע"])
        self.assertTrue(all(sheet.sheet_view.rightToLeft for sheet in workbook))
        self.assertEqual(list(workbook.worksheets[0].values)[1:], [("Family", "Ari", "Needs a high chair")])
        self.assertEqual(workbook.worksheets[1]["B6"].value, 1)

    def test_group_icon_picker_saves_manual_and_distinct_automatic_icons(self):
        owner = get_user_model().objects.create_user(username="icon-test")
        event = Event.objects.create(name="Party", event_type="Birthday", owner=owner)
        self.client.force_login(owner)
        url = reverse("group_add", args=[event.pk])
        self.assertContains(self.client.get(url), 'avatar--best-friends')
        for name, icon in [("Friends", "friends"), ("Family", ""), ("Work", "")]:
            self.client.post(url, {"name": name, "icon": icon})
        icons = dict(event.groups.values_list("name", "icon"))
        self.assertEqual(icons["Friends"], "friends")
        self.assertEqual(len(set(icons.values())), 3)
        detail = self.client.get(reverse("event_detail", args=[event.pk]))
        self.assertContains(detail, 'avatar--friends')

    def test_create_event_with_split_gift_and_export(self):
        response = self.client.post(reverse("signup"), {
            "username": "event-owner",
            "email": "owner@example.com",
            "password1": "Local-example-password-789",
            "password2": "Local-example-password-789",
        })
        self.assertRedirects(response, reverse("dashboard"))
        self.assertContains(self.client.get(reverse("profile")), "owner@example.com")
        self.client.post(reverse("event_add"), {"name": "Birthday party", "event_type": "Birthday"})
        event = Event.objects.get(name="Birthday party")
        self.assertEqual(event.owner.username, "event-owner")
        self.client.post(reverse("group_add", args=[event.pk]), {"name": "Family"})
        group = event.groups.get()
        group_args = [event.pk, group.pk]
        for name in ("Noa Cohen", "Noa Levy"):
            self.client.post(reverse("guest_add", args=group_args), {"name": name})
        first, second = group.guests.all()
        add_url = reverse("gift_add", args=group_args)
        self.client.post(add_url, {
            "recipients": [first.pk], "payer": first.pk, "amount": "0", "method": "cash",
        })
        self.assertFalse(group.gifts.exists())
        response = self.client.post(add_url, {
            "covered_guests": [first.pk, second.pk],
            "payer": first.pk, "amount": "120.25", "method": "cash",
        })
        gift = group.gifts.get()
        gift_args = [event.pk, gift.pk]
        self.assertRedirects(response, reverse("gift_detail", args=gift_args))
        self.assertEqual(gift.description, "")
        self.assertEqual(gift.payments.get().amount, Decimal("120.25"))
        self.assertCountEqual(gift.payments.get().covered_guests.all(), [first, second])

        response = self.client.post(reverse("payment_add", args=gift_args), {
            "payer": second.pk, "amount": "79.75", "method": "transfer",
        })
        self.assertRedirects(response, reverse("gift_detail", args=gift_args))
        self.client.post(reverse("gift_edit", args=[*group_args, gift.pk]), {
            "description": "=1+1", "recipients": [first.pk, second.pk],
        })

        detail_url = reverse("event_actions", args=[event.pk])
        statistics_url = reverse("event_statistics", args=[event.pk])
        result = self.client.get(detail_url, {"q": "Noa"})
        self.assertEqual(result.context["gifts"].get().currency_totals, [("₪", Decimal("200.00"))])
        result = self.client.get(detail_url, {"group": group.pk, "method": "cash"})
        self.assertEqual(len(result.context["gifts"]), 1)
        self.assertEqual(result.context["results_totals"], [("₪", Decimal("120.25"))])
        self.assertFalse(self.client.get(detail_url, {"method": "check"}).context["gifts"])
        self.assertContains(result, statistics_url)
        self.assertNotContains(result, "Payment breakdown")
        statistics = self.client.get(statistics_url)
        self.assertEqual(statistics.context["total"], [("₪", Decimal("200.00"))])
        self.assertEqual(statistics.context["breakdown"], [
            ("Cash", "₪", Decimal("120.25")), ("Bank transfer", "₪", Decimal("79.75")),
        ])
        dashboard = self.client.get(reverse("dashboard"), {"q": "no matching event"})
        self.assertEqual(dashboard.context["event_count"], 1)
        self.assertNotContains(dashboard, "Total received")

        response = self.client.get(reverse("event_export", args=[event.pk]))
        workbook = load_workbook(BytesIO(b"".join(response.streaming_content)))
        self.assertEqual(workbook.sheetnames, ["Payments", "Statistics"])
        self.assertEqual(workbook["Payments"]["D2"].value, 120.25)
        self.assertEqual(workbook["Payments"].max_row, 3)

        payment = gift.payments.order_by("pk").first()
        payment_args = [*gift_args, payment.pk]
        self.client.post(reverse("payment_edit", args=payment_args), {
            "payer": first.pk, "amount": "20.25", "method": "cash", "currency": "EUR",
        })
        self.assertEqual(self.client.get(statistics_url).context["total"], [("₪", Decimal("79.75")), ("€", Decimal("20.25"))])
        filtered = self.client.get(detail_url, {"currency": "EUR", "method": "cash"})
        self.assertEqual(filtered.context["gifts"].get().currency_totals, [("€", Decimal("20.25"))])
        self.assertFalse(self.client.get(detail_url, {"currency": "EUR", "method": "transfer"}).context["gifts"])
        filtered_export = self.client.get(reverse("event_export", args=[event.pk]), {"currency": "EUR"})
        filtered_workbook = load_workbook(BytesIO(b"".join(filtered_export.streaming_content)))
        self.assertEqual(filtered_workbook["Payments"].max_row, 2)
        self.assertEqual(filtered_workbook["Payments"]["D2"].value, 20.25)
        self.assertEqual(filtered_workbook["Statistics"]["C8"].value, 20.25)
        self.client.post(reverse("payment_delete", args=payment_args))
        self.assertEqual(self.client.get(statistics_url).context["total"], [("₪", Decimal("79.75"))])
        response = self.client.post(add_url, {
            "recipients": [first.pk], "payer": first.pk, "amount": "50",
            "method": "cash", "add_another": "1",
        })
        self.assertRedirects(response, add_url)
        self.assertContains(self.client.get(add_url), "autofocus")
        self.assertEqual(group.gifts.count(), 2)
        self.client.post(reverse("event_delete", args=[event.pk]))
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())
        self.assertFalse(Payment.objects.exists())

        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))
        response = self.client.post(reverse("login"), {
            "username": "event-owner", "password": "Local-example-password-789",
        })
        self.assertRedirects(response, reverse("dashboard"))

    def test_group_setup_can_save_guests_and_defer_payments(self):
        owner = get_user_model().objects.create_user(username="group-planner")
        event = Event.objects.create(name="Party", owner=owner)
        self.client.force_login(owner)
        response = self.client.post(reverse("group_add", args=[event.pk]), {
            "name": "Family", "notes": "High chair", "save_without_payments": "1",
            "guests-TOTAL_FORMS": "1", "guests-INITIAL_FORMS": "0",
            "guests-0-name": "Ari", "guests-0-payer": "on", "guests-0-amount": "unfinished",
        })
        self.assertRedirects(response, reverse("event_detail", args=[event.pk]))
        group = event.groups.get()
        self.assertEqual(group.guests.get().name, "Ari")
        self.assertEqual(group.notes, "High chair")
        self.assertFalse(group.gifts.exists())

    def test_group_setup_records_payers_and_exports_only_filtered_payments(self):
        owner = get_user_model().objects.create_user(username="group-setup-test")
        event = Event.objects.create(name="Party", event_type="Birthday", owner=owner)
        self.client.force_login(owner)
        response = self.client.post(reverse("group_add", args=[event.pk]), {
            "name": "Family", "icon": "family",
            "guests-TOTAL_FORMS": "3", "guests-INITIAL_FORMS": "0",
            "guests-0-name": "Ari", "guests-0-payer": "on", "guests-0-amount": "150",
            "guests-0-method": "cash", "guests-0-covered": ["0", "2"],
            "guests-0-amount_1": "25", "guests-0-method_1": "card",
            "guests-1-name": "Noa", "guests-1-payer": "on", "guests-1-amount": "80",
            "guests-1-method": "card", "guests-1-covered": ["1"],
            "guests-2-name": "Lee",
        })
        self.assertRedirects(response, reverse("event_detail", args=[event.pk]))
        gift = event.groups.get().gifts.get()
        self.assertEqual(gift.payments.count(), 3)
        self.assertEqual(gift.payments.get(method="card", amount=25).covered_guests.count(), 2)
        self.assertEqual(gift.payments.get(method="cash").covered_guests.count(), 2)
        export = self.client.get(reverse("event_export", args=[event.pk]), {"method": "cash"})
        sheet = load_workbook(BytesIO(b"".join(export.streaming_content))).active
        self.assertEqual(list(sheet.values)[1:], [("Family", "Ari", "2 (Ari, Lee)", 150, "Cash")])

    def test_owner_scope_and_invalid_related_records(self):
        users = get_user_model().objects
        owner = users.create_user(username="owner")
        outsider = users.create_user(username="outsider")
        event = Event.objects.create(name="Private event", event_type="Wedding", owner=owner)
        foreign_event = Event.objects.create(name="Other event", event_type="Other", owner=outsider)
        group = GuestGroup.objects.create(name="Family", event=event)
        foreign_group = GuestGroup.objects.create(name="Friends", event=foreign_event)
        guest = Guest.objects.create(name="Owner guest", group=group)
        foreign_guest = Guest.objects.create(name="Other guest", group=foreign_group)
        gift = Gift.objects.create(description="Private gift", group=group)
        payment = Payment.objects.create(gift=gift, payer=guest, amount=10, method="cash")

        detail_url = reverse("event_detail", args=[event.pk])
        self.assertRedirects(self.client.get(detail_url), f"{reverse('login')}?next={detail_url}")
        self.client.force_login(outsider)
        self.assertNotContains(self.client.get(reverse("dashboard")), "Private event")
        for route, args in [
            ("event_detail", [event.pk]), ("event_export", [event.pk]),
            ("event_statistics", [event.pk]),
            ("event_edit", [event.pk]), ("event_delete", [event.pk]),
            ("group_edit", [event.pk, group.pk]), ("guest_edit", [event.pk, group.pk, guest.pk]),
            ("gift_detail", [event.pk, gift.pk]), ("gift_edit", [event.pk, group.pk, gift.pk]),
            ("payment_edit", [event.pk, gift.pk, payment.pk]),
        ]:
            with self.subTest(route=route):
                url = reverse(route, args=args)
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.get(reverse("gift_detail", args=[foreign_event.pk, gift.pk])).status_code, 404)

        self.client.force_login(owner)
        payment_url = reverse("payment_add", args=[event.pk, gift.pk])
        bad_coverage = self.client.post(payment_url, {
            "payer": guest.pk, "amount": "1", "method": "cash", "covered_guests": [foreign_guest.pk],
        })
        self.assertIn("covered_guests", bad_coverage.context["form"].errors)
        bad_payer = self.client.post(payment_url, {"payer": foreign_guest.pk, "amount": "1", "method": "cash"})
        self.assertIn("payer", bad_payer.context["form"].errors)
        bad_amount = self.client.post(payment_url, {"payer": guest.pk, "amount": "0", "method": "cash"})
        self.assertTrue(bad_amount.context["form"].errors)
        self.assertEqual(gift.payments.count(), 1)
        restricted = self.client.post(reverse("guest_delete", args=[event.pk, group.pk, guest.pk]))
        self.assertContains(restricted, "Update that payment first")
        self.assertTrue(Guest.objects.filter(pk=guest.pk).exists())
