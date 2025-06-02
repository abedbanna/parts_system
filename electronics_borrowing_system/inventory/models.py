from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel, ActiveManager


class Category(TimestampedModel):
    """Electronic parts categories"""
    name_ar = models.CharField(_('Name (Arabic)'), max_length=100)
    name_en = models.CharField(_('Name (English)'), max_length=100)
    description_ar = models.TextField(_('Description (Arabic)'), blank=True)
    description_en = models.TextField(_('Description (English)'), blank=True)
    icon = models.CharField(_('Icon Class'), max_length=50, default='fas fa-microchip')
    is_active = models.BooleanField(_('Active'), default=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['name_ar']

    def __str__(self):
        return self.name_ar


class ElectronicPart(TimestampedModel):
    """Electronic parts/components inventory"""
    name_ar = models.CharField(_('Name (Arabic)'), max_length=200)
    name_en = models.CharField(_('Name (English)'), max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name=_('Category'))
    part_number = models.CharField(_('Part Number'), max_length=100, unique=True)
    description_ar = models.TextField(_('Description (Arabic)'), blank=True)
    description_en = models.TextField(_('Description (English)'), blank=True)

    # Inventory tracking
    total_quantity = models.PositiveIntegerField(_('Total Quantity'), default=0)
    available_quantity = models.PositiveIntegerField(_('Available Quantity'), default=0)
    borrowed_quantity = models.PositiveIntegerField(_('Borrowed Quantity'), default=0)
    damaged_quantity = models.PositiveIntegerField(_('Damaged Quantity'), default=0)

    # Part details
    brand = models.CharField(_('Brand'), max_length=100, blank=True)
    model = models.CharField(_('Model'), max_length=100, blank=True)
    specifications = models.TextField(_('Specifications'), blank=True)
    location = models.CharField(_('Storage Location'), max_length=100, blank=True)

    # Borrowing settings
    max_borrow_days = models.PositiveIntegerField(_('Max Borrow Days'), default=7)
    max_quantity_per_user = models.PositiveIntegerField(_('Max Quantity Per User'), default=1)
    requires_approval = models.BooleanField(_('Requires Approval'), default=False)

    # Media
    image = models.ImageField(_('Image'), upload_to='parts/', blank=True, null=True)
    datasheet = models.FileField(_('Datasheet'), upload_to='datasheets/', blank=True, null=True)

    is_active = models.BooleanField(_('Active'), default=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        verbose_name = _('Electronic Part')
        verbose_name_plural = _('Electronic Parts')
        ordering = ['name_ar']

    def __str__(self):
        return f"{self.name_ar} ({self.part_number})"

    @property
    def is_available(self):
        return self.available_quantity > 0

    def update_quantities(self):
        """Update quantities based on current borrowings"""
        from borrowing.models import BorrowRecord
        active_borrows = BorrowRecord.objects.filter(
            part=self,
            status__in=['pending', 'approved', 'borrowed']
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0

        self.borrowed_quantity = active_borrows
        self.available_quantity = self.total_quantity - self.borrowed_quantity - self.damaged_quantity
        self.save()
