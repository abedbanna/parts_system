# ============================================================================
# inventory/models.py (Create this new app)
# ============================================================================

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class TimestampedModel(models.Model):
    """Abstract base model with timestamp fields"""
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        abstract = True


class Category(TimestampedModel):
    """Electronic parts categories"""
    name_ar = models.CharField(_('Arabic Name'), max_length=100)
    name_en = models.CharField(_('English Name'), max_length=100)
    description = models.TextField(_('Description'), blank=True)
    icon = models.CharField(_('Icon Class'), max_length=50, default='fas fa-microchip')
    is_active = models.BooleanField(_('Is Active'), default=True)

    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['name_ar']

    def __str__(self):
        return self.name_ar

    @property
    def name(self):
        """Return name based on current language"""
        from django.utils.translation import get_language
        if get_language() == 'ar':
            return self.name_ar
        return self.name_en


class ElectronicPart(TimestampedModel):
    """Electronic parts inventory"""

    CONDITION_CHOICES = [
        ('excellent', _('Excellent')),
        ('good', _('Good')),
        ('fair', _('Fair')),
        ('damaged', _('Damaged')),
        ('out_of_order', _('Out of Order')),
    ]

    STATUS_CHOICES = [
        ('available', _('Available')),
        ('borrowed', _('Borrowed')),
        ('maintenance', _('Under Maintenance')),
        ('discontinued', _('Discontinued')),
    ]

    # Basic Information
    name_ar = models.CharField(_('Arabic Name'), max_length=200)
    name_en = models.CharField(_('English Name'), max_length=200)
    description_ar = models.TextField(_('Arabic Description'), blank=True)
    description_en = models.TextField(_('English Description'), blank=True)

    # Classification
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        verbose_name=_('Category'),
        related_name='parts'
    )
    part_number = models.CharField(_('Part Number'), max_length=100, unique=True)
    manufacturer = models.CharField(_('Manufacturer'), max_length=100, blank=True)
    model = models.CharField(_('Model'), max_length=100, blank=True)

    # Inventory Management
    total_quantity = models.PositiveIntegerField(_('Total Quantity'), default=1)
    available_quantity = models.PositiveIntegerField(_('Available Quantity'), default=1)
    minimum_stock = models.PositiveIntegerField(_('Minimum Stock'), default=1)

    # Condition and Status
    condition = models.CharField(
        _('Condition'),
        max_length=20,
        choices=CONDITION_CHOICES,
        default='excellent'
    )
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='available'
    )

    # Physical Properties
    location = models.CharField(_('Storage Location'), max_length=100, blank=True)
    shelf_number = models.CharField(_('Shelf Number'), max_length=50, blank=True)

    # Purchase Information
    purchase_date = models.DateField(_('Purchase Date'), null=True, blank=True)
    purchase_price = models.DecimalField(
        _('Purchase Price'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    supplier = models.CharField(_('Supplier'), max_length=100, blank=True)

    # Technical Specifications (JSON field for flexibility)
    specifications = models.JSONField(_('Technical Specifications'), default=dict, blank=True)

    # Images
    image = models.ImageField(_('Image'), upload_to='parts/', blank=True, null=True)

    # Administrative
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('Added By'),
        related_name='added_parts'
    )
    notes = models.TextField(_('Notes'), blank=True)
    is_active = models.BooleanField(_('Is Active'), default=True)

    class Meta:
        verbose_name = _('Electronic Part')
        verbose_name_plural = _('Electronic Parts')
        ordering = ['name_ar']

    def __str__(self):
        return f"{self.name_ar} ({self.part_number})"

    @property
    def name(self):
        """Return name based on current language"""
        from django.utils.translation import get_language
        if get_language() == 'ar':
            return self.name_ar
        return self.name_en

    @property
    def description(self):
        """Return description based on current language"""
        from django.utils.translation import get_language
        if get_language() == 'ar':
            return self.description_ar
        return self.description_en

    @property
    def is_low_stock(self):
        """Check if part is low on stock"""
        return self.available_quantity <= self.minimum_stock

    @property
    def is_available_for_borrowing(self):
        """Check if part can be borrowed"""
        return (
                self.status == 'available' and
                self.available_quantity > 0 and
                self.condition in ['excellent', 'good'] and
                self.is_active
        )

    def can_borrow(self, quantity=1):
        """Check if specific quantity can be borrowed"""
        return (
                self.is_available_for_borrowing and
                self.available_quantity >= quantity
        )

    def borrow(self, quantity=1):
        """Borrow parts (reduce available quantity)"""
        if self.can_borrow(quantity):
            self.available_quantity -= quantity
            if self.available_quantity == 0:
                self.status = 'borrowed'
            self.save()
            return True
        return False

    def return_parts(self, quantity=1, condition='excellent'):
        """Return borrowed parts"""
        self.available_quantity += quantity
        if self.available_quantity <= self.total_quantity:
            self.status = 'available'

        # Update condition if parts are damaged
        if condition in ['damaged', 'out_of_order']:
            self.condition = condition
            if condition == 'out_of_order':
                self.status = 'maintenance'

        self.save()


class InventoryTransaction(TimestampedModel):
    """Track inventory changes"""

    TRANSACTION_TYPES = [
        ('add', _('Added to Inventory')),
        ('remove', _('Removed from Inventory')),
        ('borrow', _('Borrowed')),
        ('return', _('Returned')),
        ('damaged', _('Marked as Damaged')),
        ('repair', _('Repaired')),
        ('adjustment', _('Inventory Adjustment')),
    ]

    part = models.ForeignKey(
        ElectronicPart,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    transaction_type = models.CharField(
        _('Transaction Type'),
        max_length=20,
        choices=TRANSACTION_TYPES
    )
    quantity = models.IntegerField(_('Quantity'))  # Can be negative for removals
    previous_quantity = models.PositiveIntegerField(_('Previous Quantity'))
    new_quantity = models.PositiveIntegerField(_('New Quantity'))

    # Who performed the transaction
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('Performed By')
    )

    # Additional context
    reason = models.TextField(_('Reason/Notes'), blank=True)
    reference_id = models.CharField(_('Reference ID'), max_length=100, blank=True)  # Link to borrow request

    class Meta:
        verbose_name = _('Inventory Transaction')
        verbose_name_plural = _('Inventory Transactions')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.part.name_ar} - {self.get_transaction_type_display()} ({self.quantity})"


class PartSpecification(models.Model):
    """Flexible specifications for parts"""
    part = models.ForeignKey(
        ElectronicPart,
        on_delete=models.CASCADE,
        related_name='specs'
    )
    name = models.CharField(_('Specification Name'), max_length=100)
    value = models.CharField(_('Value'), max_length=200)
    unit = models.CharField(_('Unit'), max_length=50, blank=True)

    class Meta:
        verbose_name = _('Part Specification')
        verbose_name_plural = _('Part Specifications')
        unique_together = ['part', 'name']

    def __str__(self):
        unit_str = f" {self.unit}" if self.unit else ""
        return f"{self.name}: {self.value}{unit_str}"


# Signal handlers for automatic inventory tracking
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


@receiver(post_save, sender=ElectronicPart)
def log_inventory_change(sender, instance, created, **kwargs):
    """Log inventory changes"""
    if created:
        # Log initial inventory addition
        InventoryTransaction.objects.create(
            part=instance,
            transaction_type='add',
            quantity=instance.total_quantity,
            previous_quantity=0,
            new_quantity=instance.total_quantity,
            performed_by=instance.added_by,
            reason='Initial inventory addition'
        )
