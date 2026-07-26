"""
api/admin.py

All Django admin site registrations in one module.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from api.models import (
    User, Customer, WalkInCustomer, Console, Game, ConsoleGame, Promotion,
    GamingSession, Booking, InventoryCategory, Supplier, InventoryItem,
    StockMovement, Sale, SaleItem, Payment, ExpenseCategory, Expense,
    Tournament, TournamentParticipant, TournamentMatch, Wallet,
    WalletTransaction, BettingMarket, Bet, Notification, SystemSetting, AuditLog,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Gaming Lounge', {'fields': ('role', 'phone_number', 'avatar', 'is_active_shift')}),
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'email', 'is_vip', 'total_spent', 'loyalty_points')
    search_fields = ('first_name', 'last_name', 'phone_number', 'email')
    list_filter = ('is_vip',)


@admin.register(WalkInCustomer)
class WalkInCustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'visit_count', 'is_converted', 'created_at')
    list_filter = ('is_converted',)


class ConsoleGameInline(admin.TabularInline):
    model = ConsoleGame
    extra = 1


@admin.register(Console)
class ConsoleAdmin(admin.ModelAdmin):
    list_display = ('console_number', 'console_type', 'status', 'hourly_rate', 'assigned_tv')
    list_filter = ('console_type', 'status')
    search_fields = ('console_number', 'assigned_tv')
    inlines = [ConsoleGameInline]


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('title', 'genre', 'publisher', 'release_year', 'times_played')
    list_filter = ('genre', 'supports_multiplayer')
    search_fields = ('title', 'publisher')


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'discount_type', 'value', 'is_active', 'start_date', 'end_date')
    list_filter = ('discount_type', 'is_active')


@admin.register(GamingSession)
class GamingSessionAdmin(admin.ModelAdmin):
    list_display = ('console', 'status', 'start_time', 'end_time', 'total_amount', 'is_paid')
    list_filter = ('status', 'is_paid')
    date_hierarchy = 'start_time'
    autocomplete_fields = ('console', 'game', 'customer')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('console', 'guest_name', 'start_time', 'end_time', 'status', 'deposit_paid')
    list_filter = ('status',)
    date_hierarchy = 'start_time'


@admin.register(InventoryCategory)
class InventoryCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'email')


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'stock_quantity', 'reorder_level', 'selling_price', 'is_sellable')
    list_filter = ('category', 'is_sellable')
    search_fields = ('name', 'sku')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'movement_type', 'quantity_change', 'resulting_quantity', 'created_at')
    list_filter = ('movement_type',)


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'status', 'total_amount', 'sold_by', 'created_at')
    list_filter = ('status',)
    search_fields = ('receipt_number',)
    inlines = [SaleItemInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('reference_code', 'method', 'status', 'amount', 'paid_at')
    list_filter = ('method', 'status')
    search_fields = ('reference_code',)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('description', 'category', 'amount', 'incurred_on', 'recorded_by')
    list_filter = ('category',)
    date_hierarchy = 'incurred_on'


class TournamentParticipantInline(admin.TabularInline):
    model = TournamentParticipant
    extra = 0


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('name', 'game', 'status', 'start_date', 'prize_pool', 'max_participants')
    list_filter = ('status', 'game')
    inlines = [TournamentParticipantInline]


@admin.register(TournamentMatch)
class TournamentMatchAdmin(admin.ModelAdmin):
    list_display = ('tournament', 'round_number', 'player_one', 'player_two', 'status', 'scheduled_time')
    list_filter = ('status',)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('customer', 'balance', 'is_locked')


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'transaction_type', 'amount', 'balance_after', 'created_at')
    list_filter = ('transaction_type',)


@admin.register(BettingMarket)
class BettingMarketAdmin(admin.ModelAdmin):
    list_display = ('question', 'match', 'status', 'odds_player_one', 'odds_player_two')
    list_filter = ('status',)


@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = ('customer', 'market', 'stake_amount', 'status', 'potential_payout')
    list_filter = ('status',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'notification_type', 'recipient', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'description')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'model_name', 'object_id', 'actor', 'created_at')
    list_filter = ('action', 'model_name')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False