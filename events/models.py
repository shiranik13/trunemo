from django.conf import settings
from django.db import models
from django.utils.translation import gettext, gettext_lazy as _


class Event(models.Model):
    class Icon(models.TextChoices):
        RINGS = "rings", _("Wedding")
        CAKE = "cake", _("Birthday")
        TOAST = "toast", _("Toast")
        GRADUATION = "graduation", _("Graduation")
        BABY = "baby", _("Baby celebration")
        STAR = "star", _("Star of David")
        CONFETTI = "confetti", _("Confetti")
        PEOPLE = "people", _("Gathering")
        GIFT = "gift", _("Gift")
        CALENDAR = "calendar", _("Calendar")

    name = models.CharField(max_length=200)
    icon = models.CharField(max_length=16, choices=Icon.choices, blank=True)
    event_date = models.DateField(blank=True, null=True)
    last_edited_at = models.DateTimeField(null=True, blank=True, editable=False)
    venue = models.CharField(max_length=200, blank=True)
    notes = models.TextField(max_length=1000, blank=True)
    event_type = models.CharField(max_length=100)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class GuestGroup(models.Model):
    class Icon(models.TextChoices):
        TWO_MOMS = "two-moms", _("Two moms with a child")
        TWO_DADS = "two-dads", _("Two dads with a child")
        DAD_DAUGHTER = "dad-daughter", _("Dad and daughter")
        MOM_SON = "mom-son", _("Mom and son")
        TWINS = "twins", _("Family with twins")
        GENERATIONS = "generations", _("Three generations")
        SIBLINGS = "siblings", _("Siblings")
        BABY = "baby", _("Parent and baby")
        BIG_FAMILY = "big-family", _("Family with three children")
        COUPLE = "couple", _("Couple")
        FAMILY = "family", _("Family")
        FRIENDS = "friends", _("Friends")
        GRANDFATHER = "grandfather", _("Grandfather")
        GRANDMOTHER = "grandmother", _("Grandmother")
        GRANDPARENTS = "grandparents", _("Grandparents")
        GENTLEMAN = "gentleman", _("Gentleman")
        LADY = "lady", _("Lady")
        BEST_FRIENDS = "best-friends", _("Best friends")
        TWO_GROOMS = "two-grooms", _("Two grooms")
        TWO_BRIDES = "two-brides", _("Two brides")
        BOY = "boy", _("Boy with a rocket")
        GIRL = "girl", _("Girl with a flower")
        YOUNG_WOMAN = "young-woman", _("Young woman")
        TATTOO = "tattoo", _("Tattooed elephant")
        PRIDE = "pride", _("Elephant with a pride pin")
        CHEF = "chef", _("Chef")
        MUSICIAN = "musician", _("Musician")

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="groups")
    name = models.CharField(max_length=150)
    notes = models.TextField(blank=True, max_length=1000)
    icon = models.CharField(max_length=12, choices=Icon.choices, blank=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class Guest(models.Model):
    group = models.ForeignKey(GuestGroup, on_delete=models.CASCADE, related_name="guests")
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class Gift(models.Model):
    group = models.ForeignKey(GuestGroup, on_delete=models.CASCADE, related_name="gifts")
    description = models.CharField(max_length=200, blank=True)
    recipients = models.ManyToManyField(Guest, through="GiftRecipient", related_name="gifts")

    def __str__(self):
        return gettext("Gift #%(number)s") % {"number": self.pk}

    @property
    def currency_totals(self):
        return [
            (symbol, amount)
            for code, symbol in Payment.Currency.choices
            if (amount := getattr(self, f"total_{code.lower()}"))
        ]


class GiftRecipient(models.Model):
    gift = models.ForeignKey(Gift, on_delete=models.CASCADE)
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["gift", "guest"], name="unique_gift_recipient"),
        ]


class Payment(models.Model):
    class Currency(models.TextChoices):
        ILS = "ILS", "₪"
        EUR = "EUR", "€"
        USD = "USD", "US$"
        GBP = "GBP", "£"
        CAD = "CAD", "CA$"
        AUD = "AUD", "AU$"
        CHF = "CHF", "CHF"
        RUB = "RUB", "₽"

    class Method(models.TextChoices):
        CASH = "cash", _("Cash")
        CARD = "card", _("Credit card")
        TRANSFER = "transfer", _("Bank transfer")
        CHECK = "check", _("Check")
        APP = "app", _("Payment app")
        OTHER = "other", _("Other")

    gift = models.ForeignKey(Gift, on_delete=models.CASCADE, related_name="payments")
    payer = models.ForeignKey(Guest, on_delete=models.RESTRICT, related_name="payments")
    covered_guests = models.ManyToManyField(Guest, blank=True, related_name="covered_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.ILS)
    method = models.CharField(max_length=12, choices=Method.choices)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="positive_payment_amount"),
        ]
