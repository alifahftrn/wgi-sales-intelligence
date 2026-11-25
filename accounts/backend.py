from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password, make_password
from .models import User

class EmailBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not isinstance(username, str) or not isinstance(password, str):
            return None
        email = username.strip()
        if not email or len(email) > 150 or not password or len(password) > 1024:
            return None
        matches = list(User.objects.using('default').filter(email__iexact=email).order_by('id')[:2])
        if len(matches) != 1:
            make_password(password)  # dummy work for missing/duplicate accounts
            return None
        user = matches[0]
        # Never compare plaintext or silently upgrade credentials in source database.
        try:
            valid = check_password(password, user.password)
        except (ValueError, TypeError):
            valid = False
        return user if valid and user.is_active else None

    def get_user(self, user_id):
        try:
            user = User.objects.using('default').get(pk=user_id)
        except User.DoesNotExist:
            return None
        return user if user.is_active else None
