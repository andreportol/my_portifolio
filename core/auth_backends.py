from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend


class EmailBackend(BaseBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        User = get_user_model()
        email = email or kwargs.get('username')

        if not email or not password:
            return None

        user = (
            User.objects.filter(email__iexact=email).order_by('id').first()
            or User.objects.filter(username__iexact=email).order_by('id').first()
        )
        if user is None:
            return None
        if not user.is_active:
            return None
        if user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
