from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models
from .policy import allowed_role

class User(AbstractBaseUser):
    """Existing MySQL table, not owned by Django migrations."""
    last_login = None
    id = models.AutoField(primary_key=True, db_column='idPengguna')
    name = models.CharField(max_length=100, db_column='namaPengguna')
    email = models.EmailField(max_length=150)
    role = models.CharField(max_length=30, db_column='peran')
    password = models.CharField(max_length=255)
    USERNAME_FIELD = 'id'  # Real unique identifier; backend handles email separately.
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    @property
    def is_active(self):
        return allowed_role(self.role)

    class Meta:
        managed = False
        db_table = 'pengguna'
