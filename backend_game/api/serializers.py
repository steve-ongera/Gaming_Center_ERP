"""
api/serializers.py

All DRF serializers, grouped by domain. List/detail split is used where a
lighter payload materially helps list-endpoint performance (e.g. sessions,
sales); otherwise a single serializer is reused for read and write.
"""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from api.models import (
    User, Customer, WalkInCustomer, Console, Game, ConsoleGame, Promotion,
    GamingSession, Booking, InventoryCategory, Supplier, InventoryItem,
    StockMovement, Sale, SaleItem, Payment, ExpenseCategory, Expense,
    Tournament, TournamentParticipant, TournamentMatch, Wallet,
    WalletTransaction, BettingMarket, Bet, Notification, SystemSetting, AuditLog,
)


# ===========================================================================
# USERS & AUTH
# ===========================================================================
class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'phone_number', 'avatar', 'is_active', 'is_active_shift', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'password']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])


# ===========================================================================
# CUSTOMERS
# ===========================================================================
class CustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id', 'first_name', 'last_name', 'full_name', 'phone_number', 'email',
            'date_of_birth', 'loyalty_points', 'total_spent', 'is_vip', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'loyalty_points', 'total_spent', 'created_at', 'updated_at']


class WalkInCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalkInCustomer
        fields = ['id', 'name', 'phone_number', 'visit_count', 'is_converted', 'created_at']
        read_only_fields = ['id', 'is_converted', 'created_at']


class ConvertWalkInSerializer(serializers.Serializer):
    walk_in_customer_id = serializers.UUIDField()
    phone_number = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField(required=False, allow_blank=True)


# ===========================================================================
# CONSOLES & GAMES
# ===========================================================================
class GameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = [
            'id', 'title', 'category', 'genre', 'publisher', 'release_year',
            'supports_multiplayer', 'max_players', 'cover_image', 'times_played',
        ]
        read_only_fields = ['id', 'times_played']


class ConsoleGameSerializer(serializers.ModelSerializer):
    game_title = serializers.CharField(source='game.title', read_only=True)

    class Meta:
        model = ConsoleGame
        fields = ['id', 'console', 'game', 'game_title', 'installed_at']


class ConsoleSerializer(serializers.ModelSerializer):
    installed_games = ConsoleGameSerializer(many=True, read_only=True)

    class Meta:
        model = Console
        fields = [
            'id', 'console_number', 'console_type', 'controller_count', 'assigned_tv',
            'hourly_rate', 'status', 'location_label', 'next_maintenance_date',
            'maintenance_notes', 'installed_games', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ConsoleListSerializer(serializers.ModelSerializer):
    """Lighter payload for dashboard/list views."""

    class Meta:
        model = Console
        fields = ['id', 'console_number', 'console_type', 'hourly_rate', 'status']


class PromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = [
            'id', 'name', 'code', 'discount_type', 'value', 'start_date', 'end_date',
            'is_active', 'max_uses', 'times_used',
        ]
        read_only_fields = ['id', 'times_used']


# ===========================================================================
# GAMING SESSIONS & BOOKINGS
# ===========================================================================
class GamingSessionSerializer(serializers.ModelSerializer):
    console_number = serializers.CharField(source='console.console_number', read_only=True)
    game_title = serializers.CharField(source='game.title', read_only=True, default=None)
    customer_name = serializers.SerializerMethodField()
    live_charge_preview = serializers.SerializerMethodField()

    class Meta:
        model = GamingSession
        fields = [
            'id', 'console', 'console_number', 'game', 'game_title', 'customer', 'walk_in_customer',
            'customer_name', 'started_by', 'closed_by', 'status', 'number_of_players',
            'hourly_rate_snapshot', 'start_time', 'end_time', 'planned_duration_minutes',
            'extra_minutes', 'promotion', 'discount_amount', 'subtotal_amount', 'total_amount',
            'is_paid', 'live_charge_preview', 'created_at',
        ]
        read_only_fields = [
            'id', 'started_by', 'closed_by', 'hourly_rate_snapshot', 'subtotal_amount',
            'total_amount', 'is_paid', 'created_at',
        ]

    def get_customer_name(self, obj):
        if obj.customer:
            return obj.customer.full_name
        if obj.walk_in_customer:
            return obj.walk_in_customer.name
        return 'Guest'

    def get_live_charge_preview(self, obj):
        if obj.status != GamingSession.Status.ACTIVE:
            return None
        from api.services import calculate_session_charges
        return calculate_session_charges(obj)


class StartSessionSerializer(serializers.Serializer):
    console_id = serializers.UUIDField()
    game_id = serializers.UUIDField(required=False, allow_null=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    walk_in_name = serializers.CharField(required=False, allow_blank=True)
    walk_in_phone = serializers.CharField(required=False, allow_blank=True)
    number_of_players = serializers.IntegerField(default=1, min_value=1)
    planned_duration_minutes = serializers.IntegerField(required=False, allow_null=True)
    promotion_code = serializers.CharField(required=False, allow_blank=True)


class BookingSerializer(serializers.ModelSerializer):
    console_number = serializers.CharField(source='console.console_number', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'console', 'console_number', 'customer', 'guest_name', 'guest_phone',
            'start_time', 'end_time', 'status', 'deposit_amount', 'deposit_paid', 'notes',
            'resulting_session', 'created_at',
        ]
        read_only_fields = ['id', 'resulting_session', 'created_at']


# ===========================================================================
# INVENTORY
# ===========================================================================
class InventoryCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryCategory
        fields = ['id', 'name', 'description']


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'phone_number', 'email', 'address']


class InventoryItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    stock_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            'id', 'name', 'sku', 'category', 'category_name', 'supplier', 'unit_type',
            'purchase_cost', 'selling_price', 'stock_quantity', 'reorder_level',
            'is_sellable', 'is_low_stock', 'stock_value', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'item', 'item_name', 'movement_type', 'quantity_change',
            'resulting_quantity', 'reference_note', 'performed_by', 'created_at',
        ]
        read_only_fields = ['id', 'resulting_quantity', 'performed_by', 'created_at']


class StockAdjustmentSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    quantity_change = serializers.IntegerField()
    movement_type = serializers.ChoiceField(choices=StockMovement.MovementType.choices)
    reference_note = serializers.CharField(required=False, allow_blank=True)


# ===========================================================================
# SALES
# ===========================================================================
class SaleItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = SaleItem
        fields = ['id', 'item', 'item_name', 'quantity', 'unit_price', 'line_total']
        read_only_fields = ['id', 'unit_price', 'line_total']


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    sold_by_name = serializers.CharField(source='sold_by.username', read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'receipt_number', 'customer', 'walk_in_customer', 'gaming_session',
            'sold_by', 'sold_by_name', 'status', 'subtotal_amount', 'discount_amount',
            'tax_amount', 'total_amount', 'items', 'created_at',
        ]
        read_only_fields = [
            'id', 'receipt_number', 'sold_by', 'subtotal_amount', 'total_amount', 'created_at',
        ]


class CreateSaleLineItemSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class CreateSaleSerializer(serializers.Serializer):
    line_items = CreateSaleLineItemSerializer(many=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    walk_in_customer_id = serializers.UUIDField(required=False, allow_null=True)
    gaming_session_id = serializers.UUIDField(required=False, allow_null=True)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)


# ===========================================================================
# PAYMENTS & EXPENSES
# ===========================================================================
class PaymentSerializer(serializers.ModelSerializer):
    received_by_name = serializers.CharField(source='received_by.username', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'reference_code', 'method', 'status', 'amount', 'gaming_session', 'sale',
            'booking', 'customer', 'received_by', 'received_by_name', 'paid_at', 'meta', 'created_at',
        ]
        read_only_fields = ['id', 'reference_code', 'received_by', 'created_at']


class RecordPaymentSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    gaming_session_id = serializers.UUIDField(required=False, allow_null=True)
    sale_id = serializers.UUIDField(required=False, allow_null=True)
    booking_id = serializers.UUIDField(required=False, allow_null=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    meta = serializers.JSONField(required=False)


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ['id', 'name']


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'category', 'category_name', 'description', 'amount', 'incurred_on',
            'recorded_by', 'receipt_attachment', 'created_at',
        ]
        read_only_fields = ['id', 'recorded_by', 'created_at']


# ===========================================================================
# TOURNAMENTS & BETTING
# ===========================================================================
class TournamentParticipantSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)

    class Meta:
        model = TournamentParticipant
        fields = ['id', 'tournament', 'customer', 'customer_name', 'seed_number', 'result', 'rank', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class TournamentMatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = TournamentMatch
        fields = [
            'id', 'tournament', 'round_number', 'player_one', 'player_two', 'scheduled_time',
            'status', 'winner', 'score_summary',
        ]
        read_only_fields = ['id']


class TournamentSerializer(serializers.ModelSerializer):
    participants = TournamentParticipantSerializer(many=True, read_only=True)
    participant_count = serializers.IntegerField(source='participants.count', read_only=True)
    game_title = serializers.CharField(source='game.title', read_only=True)

    class Meta:
        model = Tournament
        fields = [
            'id', 'name', 'game', 'game_title', 'description', 'entry_fee', 'prize_pool',
            'max_participants', 'start_date', 'end_date', 'status', 'banner_image',
            'participants', 'participant_count', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class RegisterParticipantSerializer(serializers.Serializer):
    tournament_id = serializers.UUIDField()
    customer_id = serializers.UUIDField()


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['id', 'customer', 'balance', 'is_locked']
        read_only_fields = ['id', 'balance']


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'wallet', 'transaction_type', 'amount', 'balance_after', 'reference', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'balance_after', 'created_at']


class BettingMarketSerializer(serializers.ModelSerializer):
    class Meta:
        model = BettingMarket
        fields = [
            'id', 'match', 'question', 'status', 'odds_player_one', 'odds_player_two',
            'winning_outcome', 'settled_at',
        ]
        read_only_fields = ['id', 'settled_at']


class BetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bet
        fields = [
            'id', 'market', 'customer', 'predicted_winner', 'stake_amount',
            'odds_at_placement', 'potential_payout', 'status', 'settled_at', 'created_at',
        ]
        read_only_fields = ['id', 'odds_at_placement', 'potential_payout', 'status', 'settled_at', 'created_at']


class PlaceBetSerializer(serializers.Serializer):
    market_id = serializers.UUIDField()
    customer_id = serializers.UUIDField()
    predicted_winner_id = serializers.UUIDField()
    stake_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)


# ===========================================================================
# NOTIFICATIONS, SETTINGS, AUDIT LOGS
# ===========================================================================
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'notification_type', 'title', 'message', 'is_read', 'link', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = ['id', 'key', 'value', 'description']


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'actor', 'actor_name', 'action', 'model_name', 'object_id',
            'changes', 'ip_address', 'path', 'created_at',
        ]
        read_only_fields = fields