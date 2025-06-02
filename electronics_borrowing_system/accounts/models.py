from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    USER_TYPES = (
        ('student', _('Student')),
        ('staff', _('Staff')),
        ('admin', _('Administrator')),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type = models.CharField(_('User Type'), max_length=20, choices=USER_TYPES, default='student')
    student_id = models.CharField(_('Student ID'), max_length=20, blank=True, null=True, unique=True)
    phone = models.CharField(_('Phone Number'), max_length=15, blank=True)
    department = models.CharField(_('Department'), max_length=100, blank=True)
    avatar = models.ImageField(_('Avatar'), upload_to='avatars/', blank=True, null=True)
    is_active_borrower = models.BooleanField(_('Can Borrow'), default=True)

    class Meta:
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.user.username})"

    @property
    def can_borrow(self):
        return self.user.is_active and self.is_active_borrower


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
