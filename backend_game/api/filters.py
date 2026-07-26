"""
api/filters.py

All django-filter FilterSet classes used by the DjangoFilterBackend on
views.py ViewSets. Grouped by domain, matching models.py.
"""
import django_filters as df

from api.models import (
    Console, Game, GamingSession, Customer, WalkInCustomer, Booking,
    InventoryItem, Sale, Payment, Expense, Tournament, Notification, AuditLog,
)


class ConsoleFilter(df.FilterSet):
    status = df.CharFilter(field_name='status')
    console_type = df.CharFilter(field_name='console_type')
    min_rate = df.NumberFilter(field_name='hourly_rate', lookup_expr='gte')
    max_rate = df.NumberFilter(field_name='hourly_rate', lookup_expr='lte')

    class Meta:
        model = Console
        fields = ['status', 'console_type']


class GameFilter(df.FilterSet):
    genre = df.CharFilter(field_name='genre')
    supports_multiplayer = df.BooleanFilter(field_name='supports_multiplayer')
    release_year = df.NumberFilter(field_name='release_year')

    class Meta:
        model = Game
        fields = ['genre', 'supports_multiplayer', 'release_year']


class GamingSessionFilter(df.FilterSet):
    status = df.CharFilter(field_name='status')
    console = df.UUIDFilter(field_name='console_id')
    customer = df.UUIDFilter(field_name='customer_id')
    is_walk_in = df.BooleanFilter(method='filter_is_walk_in')
    start_after = df.DateTimeFilter(field_name='start_time', lookup_expr='gte')
    start_before = df.DateTimeFilter(field_name='start_time', lookup_expr='lte')

    class Meta:
        model = GamingSession
        fields = ['status', 'console', 'customer']

    def filter_is_walk_in(self, queryset, name, value):
        return queryset.filter(customer__isnull=value)


class CustomerFilter(df.FilterSet):
    is_vip = df.BooleanFilter(field_name='is_vip')
    search_phone = df.CharFilter(field_name='phone_number', lookup_expr='icontains')

    class Meta:
        model = Customer
        fields = ['is_vip']


class WalkInCustomerFilter(df.FilterSet):
    is_converted = df.BooleanFilter(field_name='is_converted')

    class Meta:
        model = WalkInCustomer
        fields = ['is_converted']


class BookingFilter(df.FilterSet):
    status = df.CharFilter(field_name='status')
    console = df.UUIDFilter(field_name='console_id')
    date_from = df.DateTimeFilter(field_name='start_time', lookup_expr='gte')
    date_to = df.DateTimeFilter(field_name='end_time', lookup_expr='lte')

    class Meta:
        model = Booking
        fields = ['status', 'console']


class InventoryItemFilter(df.FilterSet):
    category = df.UUIDFilter(field_name='category_id')
    low_stock = df.BooleanFilter(method='filter_low_stock')
    is_sellable = df.BooleanFilter(field_name='is_sellable')

    class Meta:
        model = InventoryItem
        fields = ['category', 'is_sellable']

    def filter_low_stock(self, queryset, name, value):
        from django.db.models import F
        return queryset.filter(stock_quantity__lte=F('reorder_level')) if value else queryset


class SaleFilter(df.FilterSet):
    status = df.CharFilter(field_name='status')
    date_from = df.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = df.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = Sale
        fields = ['status']


class PaymentFilter(df.FilterSet):
    method = df.CharFilter(field_name='method')
    status = df.CharFilter(field_name='status')
    date_from = df.DateTimeFilter(field_name='paid_at', lookup_expr='gte')
    date_to = df.DateTimeFilter(field_name='paid_at', lookup_expr='lte')

    class Meta:
        model = Payment
        fields = ['method', 'status']


class ExpenseFilter(df.FilterSet):
    category = df.UUIDFilter(field_name='category_id')
    date_from = df.DateFilter(field_name='incurred_on', lookup_expr='gte')
    date_to = df.DateFilter(field_name='incurred_on', lookup_expr='lte')

    class Meta:
        model = Expense
        fields = ['category']


class TournamentFilter(df.FilterSet):
    status = df.CharFilter(field_name='status')
    game = df.UUIDFilter(field_name='game_id')

    class Meta:
        model = Tournament
        fields = ['status', 'game']


class NotificationFilter(df.FilterSet):
    is_read = df.BooleanFilter(field_name='is_read')
    notification_type = df.CharFilter(field_name='notification_type')

    class Meta:
        model = Notification
        fields = ['is_read', 'notification_type']


class AuditLogFilter(df.FilterSet):
    action = df.CharFilter(field_name='action')
    model_name = df.CharFilter(field_name='model_name')
    actor = df.UUIDFilter(field_name='actor_id')
    date_from = df.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = df.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = AuditLog
        fields = ['action', 'model_name', 'actor']