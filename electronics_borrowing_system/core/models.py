from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class TimestampedModel(models.Model):
    """Base model with created and updated timestamps"""
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        abstract = True


class ActiveManager(models.Manager):
    """Manager that returns only active records"""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
