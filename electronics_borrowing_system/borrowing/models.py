from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User  # Use standard Django User
from django.utils import timezone
from core.models import TimestampedModel


class BorrowRequest(TimestampedModel):
    """Student borrowing requests"""
    STATUS_CHOICES = (
        ('draft', _('Draft')),
        ('submitted', _('Submitted')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('borrowed', _('Borrowed')),
        ('returned', _('Returned')),
        ('overdue', _('Overdue')),
        ('damaged', _('Damaged')),
    )

    student = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('Student'))
    request_date = models.DateTimeField(_('Request Date'), auto_now_add=True)
    purpose = models.TextField(_('Purpose of Use'))
    expected_return_date = models.DateField(_('Expected Return Date'))
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='draft')

    # Approval workflow
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_requests', verbose_name=_('Approved By')
    )
    approval_date = models.DateTimeField(_('Approval Date'), null=True, blank=True)
    rejection_reason = models.TextField(_('Rejection Reason'), blank=True)

    # Borrowing details
    borrowed_date = models.DateTimeField(_('Borrowed Date'), null=True, blank=True)
    actual_return_date = models.DateTimeField(_('Actual Return Date'), null=True, blank=True)

    # Notes
    admin_notes = models.TextField(_('Admin Notes'), blank=True)
    student_notes = models.TextField(_('Student Notes'), blank=True)

    class Meta:
        verbose_name = _('Borrow Request')
        verbose_name_plural = _('Borrow Requests')
        ordering = ['-request_date']

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.request_date.strftime('%Y-%m-%d')}"

    @property
    def is_overdue(self):
        if self.status == 'borrowed' and self.expected_return_date:
            return timezone.now().date() > self.expected_return_date
        return False

    def approve(self, approved_by):
        self.status = 'approved'
        self.approved_by = approved_by
        self.approval_date = timezone.now()
        self.save()

    def reject(self, reason):
        self.status = 'rejected'
        self.rejection_reason = reason
        self.save()


class BorrowRecord(TimestampedModel):
    """Individual part borrowing records"""
    request = models.ForeignKey(BorrowRequest, on_delete=models.CASCADE, related_name='records')
    part = models.ForeignKey('inventory.ElectronicPart', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(_('Quantity'), default=1)

    # Condition tracking
    condition_borrowed = models.CharField(
        _('Condition When Borrowed'), max_length=20,
        choices=[('excellent', _('Excellent')), ('good', _('Good')), ('fair', _('Fair'))],
        default='excellent'
    )
    condition_returned = models.CharField(
        _('Condition When Returned'), max_length=20,
        choices=[('excellent', _('Excellent')), ('good', _('Good')), ('fair', _('Fair')), ('damaged', _('Damaged'))],
        blank=True
    )

    damage_description = models.TextField(_('Damage Description'), blank=True)

    class Meta:
        verbose_name = _('Borrow Record')
        verbose_name_plural = _('Borrow Records')

    def __str__(self):
        return f"{self.part.name_ar} x{self.quantity}"
