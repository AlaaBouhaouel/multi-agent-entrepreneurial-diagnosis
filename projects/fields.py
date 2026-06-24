from django.db import models

from .crypto import decrypt_text, encrypt_text


class EncryptedTextField(models.TextField):
    description = "Text field encrypted at rest"

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return decrypt_text(value)

    def to_python(self, value):
        if value is None or isinstance(value, str) is False:
            return value
        return decrypt_text(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, ""):
            return value
        return encrypt_text(value)
