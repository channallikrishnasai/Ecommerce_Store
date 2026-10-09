from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Customer(models.Model):
    stripe_customer_id = models.CharField(max_length=100, blank=True, default='')
    user = models.OneToOneField(to=User, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return self.user.email
