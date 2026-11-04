from django.contrib.auth.password_validation import MinimumLengthValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class LocalizedMinimumLengthValidator(MinimumLengthValidator):
    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                _("Use at least %(min_length)d characters."),
                code="password_too_short",
                params={"min_length": self.min_length},
            )

    def get_help_text(self):
        return _("Use at least %(min_length)d characters.") % {"min_length": self.min_length}


class EnglishPasswordValidator:
    def validate(self, password, user=None):
        if not password.isascii() or not password.isprintable():
            raise ValidationError(self.get_help_text(), code="password_invalid_characters")

    def get_help_text(self):
        return _("Use only English letters, digits, and standard keyboard symbols.")
