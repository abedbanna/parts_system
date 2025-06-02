# borrowing/models.py (Enhanced version with improvements)

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.urls import reverse
from datetime import date, timedelta
import uuid


class TimestampedModel(models.Model):
    """Abstract base model with timestamp fields"""
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        abstract = True


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
        ('cancelled', _('Cancelled')),  # Added: Students can cancel their own requests
    )

    # Add UUID for security (prevents guessing request IDs)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_('Student'),
        related_name='borrow_requests'
    )
    request_date = models.DateTimeField(_('Request Date'), auto_now_add=True)
    purpose = models.TextField(_('Purpose of Use'))
    expected_return_date = models.DateField(_('Expected Return Date'))

    # Add urgency level
    URGENCY_CHOICES = (
        ('low', _('Low')),
        ('normal', _('Normal')),
        ('high', _('High')),
        ('urgent', _('Urgent')),
    )
    urgency = models.CharField(
        _('Urgency'),
        max_length=10,
        choices=URGENCY_CHOICES,
        default='normal'
    )

    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='submitted'
    )

    # Approval workflow
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_requests',
        verbose_name=_('Approved By')
    )
    approval_date = models.DateTimeField(_('Approval Date'), null=True, blank=True)
    rejection_reason = models.TextField(_('Rejection Reason'), blank=True)

    # Borrowing details
    borrowed_date = models.DateTimeField(_('Borrowed Date'), null=True, blank=True)
    actual_return_date = models.DateTimeField(_('Actual Return Date'), null=True, blank=True)

    # Add due date reminder system
    reminder_sent = models.BooleanField(_('Reminder Sent'), default=False)
    overdue_notified = models.BooleanField(_('Overdue Notification Sent'), default=False)

    # Notes
    admin_notes = models.TextField(_('Admin Notes'), blank=True)
    student_notes = models.TextField(_('Student Notes'), blank=True)

    # Add attachment support
    attachment = models.FileField(
        _('Attachment'),
        upload_to='borrow_requests/',
        blank=True,
        help_text=_('Optional: Circuit diagram, project description, etc.')
    )

    class Meta:
        verbose_name = _('Borrow Request')
        verbose_name_plural = _('Borrow Requests')
        ordering = ['-request_date']
        # Add database indexes for better performance
        indexes = [
            models.Index(fields=['status', 'request_date']),
            models.Index(fields=['student', 'status']),
            models.Index(fields=['expected_return_date']),
        ]

    def __str__(self):
        student_name = self.student.get_full_name() or self.student.username
        return f"#{self.id} - {student_name} - {self.request_date.strftime('%Y-%m-%d')}"

    def clean(self):
        """Enhanced validation"""
        super().clean()

        # Validate expected return date
        if self.expected_return_date:
            min_date = date.today() + timedelta(days=1)
            max_date = date.today() + timedelta(days=90)  # Maximum 3 months

            if self.expected_return_date < min_date:
                raise ValidationError({
                    'expected_return_date': _('Expected return date must be at least tomorrow.')
                })

            if self.expected_return_date > max_date:
                raise ValidationError({
                    'expected_return_date': _('Expected return date cannot be more than 3 months from now.')
                })

        # Validate status transitions
        if self.pk:  # Only for existing instances
            old_instance = BorrowRequest.objects.get(pk=self.pk)
            if not self._is_valid_status_transition(old_instance.status, self.status):
                raise ValidationError({
                    'status': _('Invalid status transition from {} to {}.').format(
                        old_instance.get_status_display(),
                        self.get_status_display()
                    )
                })

    def _is_valid_status_transition(self, from_status, to_status):
        """Define valid status transitions"""
        valid_transitions = {
            'draft': ['submitted', 'cancelled'],
            'submitted': ['approved', 'rejected', 'cancelled'],
            'approved': ['borrowed', 'cancelled'],
            'rejected': [],  # Final state
            'borrowed': ['returned', 'overdue', 'damaged'],
            'returned': [],  # Final state
            'overdue': ['returned', 'damaged'],
            'damaged': ['returned'],
            'cancelled': [],  # Final state
        }
        return to_status in valid_transitions.get(from_status, [])

    def get_absolute_url(self):
        """Get URL for this request"""
        return reverse('borrowing:request_detail', kwargs={'pk': self.pk})

    @property
    def is_overdue(self):
        """Check if the request is overdue"""
        if self.status == 'borrowed' and self.expected_return_date:
            return timezone.now().date() > self.expected_return_date
        return False

    @property
    def days_until_due(self):
        """Get days until due (negative if overdue)"""
        if self.status == 'borrowed' and self.expected_return_date:
            return (self.expected_return_date - timezone.now().date()).days
        return None

    @property
    def total_parts(self):
        """Get total number of parts in this request"""
        return self.records.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0

    @property
    def can_be_cancelled(self):
        """Check if request can be cancelled by student"""
        return self.status in ['draft', 'submitted']

    @property
    def can_be_edited(self):
        """Check if request can be edited by student"""
        return self.status == 'draft'

    def approve(self, approved_by):
        """Approve the request"""
        if self.status != 'submitted':
            raise ValidationError(_('Only submitted requests can be approved.'))

        self.status = 'approved'
        self.approved_by = approved_by
        self.approval_date = timezone.now()
        self.save()

        # Create history entry
        BorrowRequestHistory.objects.create(
            request=self,
            action='approved',
            performed_by=approved_by,
            notes=f'Request approved by {approved_by.get_full_name() or approved_by.username}'
        )

    def reject(self, rejected_by, reason):
        """Reject the request"""
        if self.status != 'submitted':
            raise ValidationError(_('Only submitted requests can be rejected.'))

        self.status = 'rejected'
        self.rejection_reason = reason
        self.save()

        # Create history entry
        BorrowRequestHistory.objects.create(
            request=self,
            action='rejected',
            performed_by=rejected_by,
            notes=f'Request rejected: {reason}'
        )

    def mark_as_borrowed(self, borrowed_by):
        """Mark request as borrowed"""
        if self.status != 'approved':
            raise ValidationError(_('Only approved requests can be marked as borrowed.'))

        self.status = 'borrowed'
        self.borrowed_date = timezone.now()
        self.save()

        # Create history entry
        BorrowRequestHistory.objects.create(
            request=self,
            action='borrowed',
            performed_by=borrowed_by,
            notes=f'Items borrowed by student'
        )

    def mark_as_returned(self, returned_by, condition_notes=""):
        """Mark request as returned"""
        if self.status not in ['borrowed', 'overdue']:
            raise ValidationError(_('Only borrowed/overdue requests can be marked as returned.'))

        self.status = 'returned'
        self.actual_return_date = timezone.now()
        self.save()

        # Create history entry
        BorrowRequestHistory.objects.create(
            request=self,
            action='returned',
            performed_by=returned_by,
            notes=f'Items returned. Condition: {condition_notes}'
        )

    def cancel(self, cancelled_by, reason=""):
        """Cancel the request"""
        if not self.can_be_cancelled:
            raise ValidationError(_('This request cannot be cancelled.'))

        self.status = 'cancelled'
        self.save()

        # Create history entry
        BorrowRequestHistory.objects.create(
            request=self,
            action='cancelled',
            performed_by=cancelled_by,
            notes=f'Request cancelled: {reason}'
        )


class BorrowRecord(TimestampedModel):
    """Individual part borrowing records"""
    CONDITION_CHOICES = [
        ('excellent', _('Excellent')),
        ('good', _('Good')),
        ('fair', _('Fair')),
        ('damaged', _('Damaged')),
        ('missing', _('Missing')),  # Added: For lost items
    ]

    request = models.ForeignKey(
        BorrowRequest,
        on_delete=models.CASCADE,
        related_name='records',
        verbose_name=_('Borrow Request')
    )

    # Part information (stored as text to handle cases where parts might not exist in inventory)
    part_name = models.CharField(_('Part Name'), max_length=200)
    part_description = models.TextField(_('Part Description'), blank=True)
    part_number = models.CharField(_('Part Number'), max_length=100, blank=True)  # Added
    quantity = models.PositiveIntegerField(_('Quantity'), default=1)

    # Add unit cost for tracking value
    unit_cost = models.DecimalField(
        _('Unit Cost'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Cost per unit for damage/loss tracking')
    )

    # Condition tracking
    condition_borrowed = models.CharField(
        _('Condition When Borrowed'),
        max_length=20,
        choices=CONDITION_CHOICES,
        default='excellent'
    )
    condition_returned = models.CharField(
        _('Condition When Returned'),
        max_length=20,
        choices=CONDITION_CHOICES,
        blank=True
    )

    damage_description = models.TextField(_('Damage Description'), blank=True)

    # Add replacement cost for damaged/missing items
    replacement_cost = models.DecimalField(
        _('Replacement Cost'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Optional reference to inventory system
    inventory_part = models.ForeignKey(
        'inventory.ElectronicPart',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Inventory Part')
    )

    # Add serial numbers for tracking specific items
    serial_numbers = models.JSONField(
        _('Serial Numbers'),
        default=list,
        blank=True,
        help_text=_('List of serial numbers for tracked items')
    )

    class Meta:
        verbose_name = _('Borrow Record')
        verbose_name_plural = _('Borrow Records')
        # Add constraint to prevent duplicate parts in same request
        unique_together = ['request', 'part_name', 'part_number']

    def __str__(self):
        return f"{self.part_name} x{self.quantity} - {self.request}"

    @property
    def is_damaged(self):
        """Check if part was returned damaged"""
        return self.condition_returned in ['damaged', 'missing']

    @property
    def total_value(self):
        """Calculate total value of this record"""
        if self.unit_cost:
            return self.unit_cost * self.quantity
        return 0

    @property
    def damage_cost(self):
        """Calculate damage/replacement cost"""
        if self.is_damaged and self.replacement_cost:
            return self.replacement_cost
        return 0

    def clean(self):
        """Enhanced validation"""
        super().clean()

        if self.quantity <= 0:
            raise ValidationError({
                'quantity': _('Quantity must be greater than 0.')
            })

        if self.unit_cost and self.unit_cost < 0:
            raise ValidationError({
                'unit_cost': _('Unit cost cannot be negative.')
            })

        if self.replacement_cost and self.replacement_cost < 0:
            raise ValidationError({
                'replacement_cost': _('Replacement cost cannot be negative.')
            })


class BorrowRequestHistory(TimestampedModel):
    """Track all actions performed on borrow requests"""
    ACTION_CHOICES = [
        ('created', _('Created')),
        ('submitted', _('Submitted')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('borrowed', _('Borrowed')),
        ('returned', _('Returned')),
        ('cancelled', _('Cancelled')),
        ('reminder_sent', _('Reminder Sent')),
        ('marked_overdue', _('Marked Overdue')),
        ('note_added', _('Note Added')),
    ]

    request = models.ForeignKey(
        BorrowRequest,
        on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(_('Action'), max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    notes = models.TextField(_('Notes'), blank=True)

    class Meta:
        verbose_name = _('Borrow Request History')
        verbose_name_plural = _('Borrow Request Histories')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_display()} - {self.request}"


# Enhanced managers and querysets
class BorrowRequestQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status='submitted')

    def approved(self):
        return self.filter(status='approved')

    def active(self):
        return self.filter(status='borrowed')

    def overdue(self):
        from datetime import date
        return self.filter(
            status='borrowed',
            expected_return_date__lt=date.today()
        )

    def due_soon(self, days=3):
        """Get requests due within specified days"""
        from datetime import date, timedelta
        due_date = date.today() + timedelta(days=days)
        return self.filter(
            status='borrowed',
            expected_return_date__lte=due_date,
            expected_return_date__gte=date.today()
        )

    def for_student(self, user):
        return self.filter(student=user)

    def by_urgency(self, urgency):
        return self.filter(urgency=urgency)

    def with_attachments(self):
        return self.exclude(attachment='')


class BorrowRequestManager(models.Manager):
    def get_queryset(self):
        return BorrowRequestQuerySet(self.model, using=self._db)

    def pending(self):
        return self.get_queryset().pending()

    def approved(self):
        return self.get_queryset().approved()

    def active(self):
        return self.get_queryset().active()

    def overdue(self):
        return self.get_queryset().overdue()

    def due_soon(self, days=3):
        return self.get_queryset().due_soon(days)


# Add the enhanced manager to the model
BorrowRequest.add_to_class('objects', BorrowRequestManager())

# Enhanced signal handlers
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


@receiver(pre_save, sender=BorrowRequest)
def create_history_on_status_change(sender, instance, **kwargs):
    """Create history entry when status changes"""
    if instance.pk:
        try:
            old_instance = BorrowRequest.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # History will be created by the action methods
                pass
        except BorrowRequest.DoesNotExist:
            pass


@receiver(post_save, sender=BorrowRecord)
def update_request_status_on_record_save(sender, instance, created, **kwargs):
    """Update request status when records are added"""
    if created and instance.request.status == 'draft':
        instance.request.status = 'submitted'
        instance.request.save()


@receiver(post_save, sender=BorrowRequest)
def create_initial_history(sender, instance, created, **kwargs):
    """Create initial history entry for new requests"""
    if created:
        BorrowRequestHistory.objects.create(
            request=instance,
            action='created',
            performed_by=instance.student,
            notes='Request created'
        )
