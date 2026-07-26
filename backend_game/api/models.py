"""
api/models.py

All database models for the Gaming Lounge ERP live in this single module,
grouped by domain with section headers. Every concrete model inherits from
BaseModel, which provides a UUID primary key, created/updated timestamps,
a soft-delete flag, and an "active" manager so deleted rows disappear from
normal querysets without ever being physically removed (audit-friendly).
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


# ===========================================================================
# BASE / MIXIN MODELS
# ===========================================================================
class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """Default manager: only returns non-deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """Escape hatch manager: returns everything, including soft-deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class BaseModel(models.Model):
    """
    Abstract base providing UUID PK, timestamps, and soft delete for every
    concrete model in the system.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


# ===========================================================================
# USERS & RBAC
# ===========================================================================
class User(AbstractUser):
    """
    Custom user model with role-based access control. Roles are coarse
    grained; fine-grained checks are performed in api/permissions.py.
    """

    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Admin'
        ADMIN = 'admin', 'Admin'
        MANAGER = 'manager', 'Manager'
        CASHIER = 'cashier', 'Cashier'
        ATTENDANT = 'attendant', 'Attendant'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ATTENDANT)
    phone_number = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    is_active_shift = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    def has_role(self, *roles):
        return self.role in roles

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


# ===========================================================================
# CUSTOMERS
# ===========================================================================
class Customer(BaseModel):
    """A registered customer with loyalty/history tracking."""
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    loyalty_points = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    is_vip = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    converted_from_walkin = models.ForeignKey(
        'WalkInCustomer', null=True, blank=True, on_delete=models.SET_NULL, related_name='converted_customer'
    )

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=['phone_number'])]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.full_name


class WalkInCustomer(BaseModel):
    """
    Lightweight, registration-free customer record. Created automatically
    when a walk-in starts a gaming session with only a name/phone. May
    later be converted into a full Customer via services.convert_walkin_to_customer.
    """
    name = models.CharField(max_length=150, blank=True, default='Guest')
    phone_number = models.CharField(max_length=20, blank=True)
    visit_count = models.PositiveIntegerField(default=1)
    is_converted = models.BooleanField(default=False)

    def __str__(self):
        return self.name or f"Walk-in {str(self.id)[:8]}"


# ===========================================================================
# CONSOLES & GAMES
# ===========================================================================
class Console(BaseModel):
    class ConsoleType(models.TextChoices):
        PS4_SLIM = 'ps4_slim', 'PS4 Slim'
        PS4_PRO = 'ps4_pro', 'PS4 Pro'
        PS5 = 'ps5', 'PS5'
        XBOX_SERIES_X = 'xbox_series_x', 'Xbox Series X'
        XBOX_SERIES_S = 'xbox_series_s', 'Xbox Series S'
        NINTENDO_SWITCH = 'switch', 'Nintendo Switch'

    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        OCCUPIED = 'occupied', 'Occupied'
        MAINTENANCE = 'maintenance', 'Maintenance'
        RESERVED = 'reserved', 'Reserved'
        OFFLINE = 'offline', 'Offline'

    console_number = models.CharField(max_length=20, unique=True)
    console_type = models.CharField(max_length=20, choices=ConsoleType.choices)
    controller_count = models.PositiveSmallIntegerField(default=2)
    assigned_tv = models.CharField(max_length=100, blank=True)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    location_label = models.CharField(max_length=100, blank=True, help_text="e.g. 'Room A - Booth 3'")
    next_maintenance_date = models.DateField(null=True, blank=True)
    maintenance_notes = models.TextField(blank=True)
    games = models.ManyToManyField('Game', through='ConsoleGame', related_name='consoles')

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=['status'])]

    def is_assignable(self):
        return self.status == self.Status.AVAILABLE

    def __str__(self):
        return f"{self.console_number} ({self.get_console_type_display()})"


class Game(BaseModel):
    class Genre(models.TextChoices):
        ACTION = 'action', 'Action'
        SPORTS = 'sports', 'Sports'
        RACING = 'racing', 'Racing'
        FIGHTING = 'fighting', 'Fighting'
        SHOOTER = 'shooter', 'Shooter'
        ADVENTURE = 'adventure', 'Adventure'
        SIMULATION = 'simulation', 'Simulation'
        SPORTS_ARCADE = 'arcade', 'Arcade'
        OTHER = 'other', 'Other'

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True)
    genre = models.CharField(max_length=20, choices=Genre.choices, default=Genre.OTHER)
    publisher = models.CharField(max_length=150, blank=True)
    release_year = models.PositiveSmallIntegerField(null=True, blank=True)
    supports_multiplayer = models.BooleanField(default=False)
    max_players = models.PositiveSmallIntegerField(default=1)
    cover_image = models.ImageField(upload_to='games/covers/', null=True, blank=True)
    times_played = models.PositiveIntegerField(default=0)

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=['title'])]

    def __str__(self):
        return self.title


class ConsoleGame(BaseModel):
    """Through model recording which games are installed on which consoles."""
    console = models.ForeignKey(Console, on_delete=models.CASCADE, related_name='installed_games')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='installations')
    installed_at = models.DateTimeField(auto_now_add=True)

    class Meta(BaseModel.Meta):
        unique_together = ('console', 'game')


# ===========================================================================
# PROMOTIONS & DISCOUNTS
# ===========================================================================
class Promotion(BaseModel):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage'
        FIXED = 'fixed', 'Fixed Amount'

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True, blank=True, null=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=8, decimal_places=2)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)

    def is_valid_now(self):
        now = timezone.now()
        if not self.is_active or not (self.start_date <= now <= self.end_date):
            return False
        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False
        return True

    def __str__(self):
        return self.name


# ===========================================================================
# GAMING SESSIONS & BOOKINGS
# ===========================================================================
class GamingSession(BaseModel):
    """
    A single billable gaming session on one console. Exactly one active
    session may exist per console at a time (enforced in services.py inside
    an atomic transaction + a partial unique constraint below).
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    console = models.ForeignKey(Console, on_delete=models.PROTECT, related_name='sessions')
    game = models.ForeignKey(Game, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    walk_in_customer = models.ForeignKey(
        WalkInCustomer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions'
    )
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='opened_sessions')
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_sessions'
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    number_of_players = models.PositiveSmallIntegerField(default=1)
    hourly_rate_snapshot = models.DecimalField(max_digits=8, decimal_places=2)

    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    planned_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    extra_minutes = models.PositiveIntegerField(default=0)

    promotion = models.ForeignKey(Promotion, on_delete=models.SET_NULL, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))

    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_paid = models.BooleanField(default=False)

    class Meta(BaseModel.Meta):
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['start_time']),
        ]
        constraints = [
            # Only one ACTIVE or PAUSED session per console at a time.
            models.UniqueConstraint(
                fields=['console'],
                condition=models.Q(status__in=['active', 'paused']),
                name='unique_active_session_per_console',
            )
        ]

    @property
    def is_walk_in(self):
        return self.customer_id is None

    def __str__(self):
        who = self.customer or self.walk_in_customer or 'Unknown'
        return f"Session on {self.console} for {who}"


class Booking(BaseModel):
    """A reservation for a future gaming slot, may or may not require a deposit."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        CHECKED_IN = 'checked_in', 'Checked In'
        CANCELLED = 'cancelled', 'Cancelled'
        NO_SHOW = 'no_show', 'No Show'

    console = models.ForeignKey(Console, on_delete=models.CASCADE, related_name='bookings')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    guest_name = models.CharField(max_length=150, blank=True)
    guest_phone = models.CharField(max_length=20, blank=True)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    deposit_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    deposit_paid = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    resulting_session = models.OneToOneField(
        GamingSession, null=True, blank=True, on_delete=models.SET_NULL, related_name='source_booking'
    )

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=['start_time', 'end_time'])]

    def __str__(self):
        return f"Booking: {self.console} @ {self.start_time:%Y-%m-%d %H:%M}"


# ===========================================================================
# INVENTORY
# ===========================================================================
class InventoryCategory(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name_plural = 'Inventory Categories'

    def __str__(self):
        return self.name


class Supplier(BaseModel):
    name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class InventoryItem(BaseModel):
    """
    Covers controllers, HDMI cables, docks, headsets, chairs, snacks,
    drinks, accessories, merchandise, and any other sellable/consumable
    stock item.
    """

    class UnitType(models.TextChoices):
        PIECE = 'piece', 'Piece'
        PACK = 'pack', 'Pack'
        BOTTLE = 'bottle', 'Bottle'
        BOX = 'box', 'Box'

    name = models.CharField(max_length=150)
    sku = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(InventoryCategory, on_delete=models.PROTECT, related_name='items')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    unit_type = models.CharField(max_length=20, choices=UnitType.choices, default=UnitType.PIECE)

    purchase_cost = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock_quantity = models.IntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=5)
    is_sellable = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=['sku']), models.Index(fields=['name'])]

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.reorder_level

    @property
    def stock_value(self):
        return self.purchase_cost * self.stock_quantity

    def __str__(self):
        return f"{self.name} ({self.sku})"


class StockMovement(BaseModel):
    class MovementType(models.TextChoices):
        RESTOCK = 'restock', 'Restock'
        SALE = 'sale', 'Sale'
        ADJUSTMENT = 'adjustment', 'Adjustment'
        DAMAGE = 'damage', 'Damage/Loss'
        RETURN = 'return', 'Return'

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity_change = models.IntegerField(help_text='Positive for additions, negative for removals')
    resulting_quantity = models.IntegerField()
    reference_note = models.CharField(max_length=255, blank=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.item} {self.movement_type} {self.quantity_change:+d}"


# ===========================================================================
# SALES
# ===========================================================================
class Sale(BaseModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    receipt_number = models.CharField(max_length=30, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    walk_in_customer = models.ForeignKey(
        WalkInCustomer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales'
    )
    gaming_session = models.ForeignKey(
        GamingSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_sales'
    )
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sales_made')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)

    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=['receipt_number'])]

    def __str__(self):
        return f"Sale {self.receipt_number}"


class SaleItem(BaseModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='sale_items')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.item.name}"


# ===========================================================================
# PAYMENTS & EXPENSES
# ===========================================================================
class Payment(BaseModel):
    class Method(models.TextChoices):
        CASH = 'cash', 'Cash'
        MPESA = 'mpesa', 'M-Pesa'
        CARD = 'card', 'Card'
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
        WALLET = 'wallet', 'Digital Wallet'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESSFUL = 'successful', 'Successful'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    reference_code = models.CharField(max_length=100, unique=True)
    method = models.CharField(max_length=20, choices=Method.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    gaming_session = models.ForeignKey(
        GamingSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments'
    )
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')

    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    paid_at = models.DateTimeField(default=timezone.now)
    meta = models.JSONField(default=dict, blank=True, help_text='Gateway-specific metadata, e.g. M-Pesa callback')

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=['reference_code']), models.Index(fields=['status'])]

    def __str__(self):
        return f"{self.get_method_display()} - {self.amount}"


class ExpenseCategory(BaseModel):
    name = models.CharField(max_length=100, unique=True)

    class Meta(BaseModel.Meta):
        verbose_name_plural = 'Expense Categories'

    def __str__(self):
        return self.name


class Expense(BaseModel):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    incurred_on = models.DateField(default=timezone.now)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    receipt_attachment = models.FileField(upload_to='expenses/receipts/', null=True, blank=True)

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=['incurred_on'])]

    def __str__(self):
        return f"{self.description} ({self.amount})"


# ===========================================================================
# TOURNAMENTS
# ===========================================================================
class Tournament(BaseModel):
    class Status(models.TextChoices):
        UPCOMING = 'upcoming', 'Upcoming'
        ONGOING = 'ongoing', 'Ongoing'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    name = models.CharField(max_length=200)
    game = models.ForeignKey(Game, on_delete=models.PROTECT, related_name='tournaments')
    description = models.TextField(blank=True)
    entry_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    prize_pool = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    max_participants = models.PositiveIntegerField(default=16)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPCOMING)
    banner_image = models.ImageField(upload_to='tournaments/banners/', null=True, blank=True)

    def __str__(self):
        return self.name


class TournamentParticipant(BaseModel):
    class Result(models.TextChoices):
        PENDING = 'pending', 'Pending'
        WINNER = 'winner', 'Winner'
        RUNNER_UP = 'runner_up', 'Runner Up'
        ELIMINATED = 'eliminated', 'Eliminated'

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='participants')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='tournament_entries')
    seed_number = models.PositiveIntegerField(null=True, blank=True)
    result = models.CharField(max_length=20, choices=Result.choices, default=Result.PENDING)
    rank = models.PositiveIntegerField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta(BaseModel.Meta):
        unique_together = ('tournament', 'customer')

    def __str__(self):
        return f"{self.customer} in {self.tournament}"


class TournamentMatch(BaseModel):
    """Schedule/bracket entry — also the anchor point for future betting markets."""

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        LIVE = 'live', 'Live'
        FINISHED = 'finished', 'Finished'
        CANCELLED = 'cancelled', 'Cancelled'

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='matches')
    round_number = models.PositiveIntegerField(default=1)
    player_one = models.ForeignKey(
        TournamentParticipant, on_delete=models.CASCADE, related_name='matches_as_p1', null=True, blank=True
    )
    player_two = models.ForeignKey(
        TournamentParticipant, on_delete=models.CASCADE, related_name='matches_as_p2', null=True, blank=True
    )
    scheduled_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    winner = models.ForeignKey(
        TournamentParticipant, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches_won'
    )
    score_summary = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.tournament} - Round {self.round_number}"


# ===========================================================================
# WALLETS & FUTURE BETTING PLATFORM
# ===========================================================================
class Wallet(BaseModel):
    """
    Digital wallet, one per customer. Underpins both future deposits/
    withdrawals for general use and the future betting platform's balance.
    """
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    is_locked = models.BooleanField(default=False)

    def __str__(self):
        return f"Wallet({self.customer}) = {self.balance}"


class WalletTransaction(BaseModel):
    class TransactionType(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposit'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'
        BET_PLACED = 'bet_placed', 'Bet Placed'
        BET_PAYOUT = 'bet_payout', 'Bet Payout'
        BONUS = 'bonus', 'Bonus'
        REFUND = 'refund', 'Refund'
        SESSION_PAYMENT = 'session_payment', 'Session Payment'

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.transaction_type} {self.amount} -> {self.balance_after}"


class BettingMarket(BaseModel):
    """
    Future module: a bettable market tied to a TournamentMatch, e.g.
    'Who wins this match?'. Modeled now so no architectural change is
    needed later to switch it on.
    """

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        SUSPENDED = 'suspended', 'Suspended'
        SETTLED = 'settled', 'Settled'
        VOID = 'void', 'Void'

    match = models.ForeignKey(TournamentMatch, on_delete=models.CASCADE, related_name='betting_markets')
    question = models.CharField(max_length=255, default='Who will win this match?')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    odds_player_one = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.90'))
    odds_player_two = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.90'))
    winning_outcome = models.ForeignKey(
        TournamentParticipant, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    settled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Market: {self.question} ({self.match})"


class Bet(BaseModel):
    class Status(models.TextChoices):
        PLACED = 'placed', 'Placed'
        WON = 'won', 'Won'
        LOST = 'lost', 'Lost'
        VOID = 'void', 'Void'

    market = models.ForeignKey(BettingMarket, on_delete=models.CASCADE, related_name='bets')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='bets')
    wallet_transaction = models.OneToOneField(
        WalletTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='bet'
    )
    predicted_winner = models.ForeignKey(TournamentParticipant, on_delete=models.CASCADE, related_name='backed_by')
    stake_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    odds_at_placement = models.DecimalField(max_digits=6, decimal_places=2)
    potential_payout = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLACED)
    settled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Bet({self.customer}, {self.stake_amount} on {self.predicted_winner})"


# ===========================================================================
# NOTIFICATIONS
# ===========================================================================
class Notification(BaseModel):
    class NotificationType(models.TextChoices):
        SESSION_STARTED = 'session_started', 'Session Started'
        SESSION_COMPLETED = 'session_completed', 'Session Completed'
        PAYMENT_RECEIVED = 'payment_received', 'Payment Received'
        LOW_STOCK = 'low_stock', 'Low Stock Alert'
        TOURNAMENT_CREATED = 'tournament_created', 'Tournament Created'
        BOOKING_REMINDER = 'booking_reminder', 'Booking Reminder'
        SYSTEM = 'system', 'System'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True
    )
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    title = models.CharField(max_length=200)
    message = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True, help_text='Frontend route to deep-link into')

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=['is_read'])]

    def __str__(self):
        return self.title


# ===========================================================================
# SETTINGS & AUDIT LOG
# ===========================================================================
class SystemSetting(BaseModel):
    """Simple key/value settings store editable from the admin portal."""
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.key


class AuditLog(models.Model):
    """
    Immutable audit trail. Deliberately NOT a BaseModel (no soft delete —
    audit rows must never be hidden or mutated). Written to by
    api/signals.py and api/middleware.py.
    """

    class Action(models.TextChoices):
        CREATE = 'create', 'Create'
        UPDATE = 'update', 'Update'
        DELETE = 'delete', 'Delete'
        LOGIN = 'login', 'Login'
        LOGOUT = 'logout', 'Logout'
        OTHER = 'other', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=Action.choices)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"[{self.action}] {self.model_name}({self.object_id}) by {self.actor}"