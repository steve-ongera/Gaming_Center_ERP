"""
api/views.py

All API endpoints in a single module. ViewSets stay thin: query
optimization (select_related/prefetch_related) happens in get_queryset,
and any real business logic is delegated to api/services.py. Every
response uses the standardized envelope from api/utils.py.
"""
from django.contrib.auth import authenticate
from rest_framework import viewsets, generics, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import (
    User, Customer, WalkInCustomer, Console, Game, ConsoleGame, Promotion,
    GamingSession, Booking, InventoryCategory, Supplier, InventoryItem,
    StockMovement, Sale, Payment, ExpenseCategory, Expense, Tournament,
    TournamentParticipant, TournamentMatch, Wallet, WalletTransaction,
    BettingMarket, Bet, Notification, SystemSetting, AuditLog,
)
from api.serializers import (
    UserSerializer, UserCreateSerializer, ChangePasswordSerializer,
    CustomerSerializer, WalkInCustomerSerializer, ConvertWalkInSerializer,
    GameSerializer, ConsoleSerializer, ConsoleListSerializer, PromotionSerializer,
    GamingSessionSerializer, StartSessionSerializer, BookingSerializer,
    InventoryCategorySerializer, SupplierSerializer, InventoryItemSerializer,
    StockMovementSerializer, StockAdjustmentSerializer, SaleSerializer,
    CreateSaleSerializer, PaymentSerializer, RecordPaymentSerializer,
    ExpenseCategorySerializer, ExpenseSerializer, TournamentSerializer,
    TournamentParticipantSerializer, RegisterParticipantSerializer,
    TournamentMatchSerializer, WalletSerializer, WalletTransactionSerializer,
    BettingMarketSerializer, BetSerializer, PlaceBetSerializer,
    NotificationSerializer, SystemSettingSerializer, AuditLogSerializer,
)
from api.permissions import (
    IsStaffRole, IsAdminOrManager, IsSuperAdmin, CanManageFinance, ReadOnlyOrStaff,
)
from api.filters import (
    ConsoleFilter, GameFilter, GamingSessionFilter, CustomerFilter,
    WalkInCustomerFilter, BookingFilter, InventoryItemFilter, SaleFilter,
    PaymentFilter, ExpenseFilter, TournamentFilter, NotificationFilter, AuditLogFilter,
)
from api import services
from api.services import ServiceError
from api.utils import success_response, error_response


# ===========================================================================
# AUTH
# ===========================================================================
class LoginView(TokenObtainPairView):
    """POST username/password -> access & refresh tokens + user profile."""
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return error_response('Invalid credentials', response.data, status.HTTP_401_UNAUTHORIZED)
        user = authenticate(
            request, username=request.data.get('username'), password=request.data.get('password')
        )
        data = {**response.data, 'user': UserSerializer(user).data if user else None}
        return success_response(data, 'Login successful')


class RefreshTokenView(TokenRefreshView):
    permission_classes = [AllowAny]


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            RefreshToken(request.data.get('refresh')).blacklist()
        except Exception:
            pass
        return success_response(message='Logged out successfully')


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data, 'Profile updated')


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return error_response('Old password is incorrect')
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return success_response(message='Password changed successfully')


# ===========================================================================
# USERS (staff management)
# ===========================================================================
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    permission_classes = [IsAdminOrManager]
    filterset_fields = ['role', 'is_active']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering_fields = ['date_joined', 'username']

    def get_serializer_class(self):
        return UserCreateSerializer if self.action == 'create' else UserSerializer


# ===========================================================================
# CUSTOMERS
# ===========================================================================
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsStaffRole]
    filterset_class = CustomerFilter
    search_fields = ['first_name', 'last_name', 'phone_number', 'email']
    ordering_fields = ['created_at', 'total_spent', 'loyalty_points']


class WalkInCustomerViewSet(viewsets.ModelViewSet):
    queryset = WalkInCustomer.objects.all()
    serializer_class = WalkInCustomerSerializer
    permission_classes = [IsStaffRole]
    filterset_class = WalkInCustomerFilter
    search_fields = ['name', 'phone_number']

    @action(detail=False, methods=['post'])
    def convert(self, request):
        serializer = ConvertWalkInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            customer = services.convert_walkin_to_customer(**serializer.validated_data)
        except ServiceError as exc:
            return error_response(str(exc))
        return success_response(CustomerSerializer(customer).data, 'Walk-in converted to customer')


# ===========================================================================
# CONSOLES & GAMES
# ===========================================================================
class ConsoleViewSet(viewsets.ModelViewSet):
    queryset = Console.objects.prefetch_related('installed_games__game')
    permission_classes = [ReadOnlyOrStaff]
    filterset_class = ConsoleFilter
    search_fields = ['console_number', 'assigned_tv', 'location_label']
    ordering_fields = ['console_number', 'hourly_rate']

    def get_serializer_class(self):
        return ConsoleListSerializer if self.action == 'list' else ConsoleSerializer


class GameViewSet(viewsets.ModelViewSet):
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    permission_classes = [ReadOnlyOrStaff]
    filterset_class = GameFilter
    search_fields = ['title', 'publisher', 'category']
    ordering_fields = ['title', 'release_year', 'times_played']


class PromotionViewSet(viewsets.ModelViewSet):
    queryset = Promotion.objects.all()
    serializer_class = PromotionSerializer
    permission_classes = [IsAdminOrManager]
    filterset_fields = ['is_active', 'discount_type']


# ===========================================================================
# GAMING SESSIONS & BOOKINGS
# ===========================================================================
class GamingSessionViewSet(viewsets.ModelViewSet):
    queryset = GamingSession.objects.select_related(
        'console', 'game', 'customer', 'walk_in_customer', 'started_by', 'closed_by', 'promotion'
    )
    serializer_class = GamingSessionSerializer
    permission_classes = [IsStaffRole]
    filterset_class = GamingSessionFilter
    ordering_fields = ['start_time', 'total_amount']

    @action(detail=False, methods=['post'])
    def start(self, request):
        serializer = StartSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = services.start_gaming_session(started_by=request.user, **serializer.validated_data)
        except ServiceError as exc:
            return error_response(str(exc))
        return success_response(GamingSessionSerializer(session).data, 'Session started', status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        try:
            session = services.stop_gaming_session(session_id=pk, closed_by=request.user)
        except ServiceError as exc:
            return error_response(str(exc))
        return success_response(GamingSessionSerializer(session).data, 'Session stopped')

    @action(detail=True, methods=['get'])
    def preview_charges(self, request, pk=None):
        session = self.get_object()
        return success_response(services.calculate_session_charges(session))


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.select_related('console', 'customer')
    serializer_class = BookingSerializer
    permission_classes = [IsStaffRole]
    filterset_class = BookingFilter
    ordering_fields = ['start_time']


# ===========================================================================
# INVENTORY
# ===========================================================================
class InventoryCategoryViewSet(viewsets.ModelViewSet):
    queryset = InventoryCategory.objects.all()
    serializer_class = InventoryCategorySerializer
    permission_classes = [IsAdminOrManager]


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAdminOrManager]


class InventoryItemViewSet(viewsets.ModelViewSet):
    queryset = InventoryItem.objects.select_related('category', 'supplier')
    serializer_class = InventoryItemSerializer
    permission_classes = [IsStaffRole]
    filterset_class = InventoryItemFilter
    search_fields = ['name', 'sku']
    ordering_fields = ['stock_quantity', 'selling_price', 'name']

    @action(detail=False, methods=['post'])
    def adjust_stock(self, request):
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = services.adjust_stock(performed_by=request.user, **serializer.validated_data)
        except ServiceError as exc:
            return error_response(str(exc))
        return success_response(InventoryItemSerializer(item).data, 'Stock adjusted')


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockMovement.objects.select_related('item', 'performed_by')
    serializer_class = StockMovementSerializer
    permission_classes = [IsStaffRole]
    filterset_fields = ['item', 'movement_type']
    ordering_fields = ['created_at']


# ===========================================================================
# SALES
# ===========================================================================
class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.select_related('customer', 'walk_in_customer', 'sold_by').prefetch_related('items__item')
    serializer_class = SaleSerializer
    permission_classes = [IsStaffRole]
    filterset_class = SaleFilter
    search_fields = ['receipt_number']
    ordering_fields = ['created_at', 'total_amount']

    def create(self, request, *args, **kwargs):
        serializer = CreateSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            sale = services.create_sale(sold_by=request.user, **serializer.validated_data)
        except ServiceError as exc:
            return error_response(str(exc))
        return success_response(SaleSerializer(sale).data, 'Sale recorded', status.HTTP_201_CREATED)


# ===========================================================================
# PAYMENTS & EXPENSES
# ===========================================================================
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('customer', 'received_by', 'gaming_session', 'sale', 'booking')
    serializer_class = PaymentSerializer
    permission_classes = [CanManageFinance]
    filterset_class = PaymentFilter
    ordering_fields = ['paid_at', 'amount']

    def create(self, request, *args, **kwargs):
        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = services.record_payment(received_by=request.user, **serializer.validated_data)
        return success_response(PaymentSerializer(payment).data, 'Payment recorded', status.HTTP_201_CREATED)


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAdminOrManager]


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.select_related('category', 'recorded_by')
    serializer_class = ExpenseSerializer
    permission_classes = [CanManageFinance]
    filterset_class = ExpenseFilter
    ordering_fields = ['incurred_on', 'amount']

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


# ===========================================================================
# TOURNAMENTS & FUTURE BETTING
# ===========================================================================
class TournamentViewSet(viewsets.ModelViewSet):
    queryset = Tournament.objects.select_related('game').prefetch_related('participants__customer')
    serializer_class = TournamentSerializer
    permission_classes = [ReadOnlyOrStaff]
    filterset_class = TournamentFilter
    search_fields = ['name']
    ordering_fields = ['start_date']

    @action(detail=False, methods=['post'])
    def register_participant(self, request):
        serializer = RegisterParticipantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            participant = services.register_tournament_participant(**serializer.validated_data)
        except ServiceError as exc:
            return error_response(str(exc))
        return success_response(TournamentParticipantSerializer(participant).data, 'Registered', status.HTTP_201_CREATED)


class TournamentMatchViewSet(viewsets.ModelViewSet):
    queryset = TournamentMatch.objects.select_related('tournament', 'player_one', 'player_two', 'winner')
    serializer_class = TournamentMatchSerializer
    permission_classes = [IsStaffRole]
    filterset_fields = ['tournament', 'status', 'round_number']


class WalletViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wallet.objects.select_related('customer')
    serializer_class = WalletSerializer
    permission_classes = [IsStaffRole]
    filterset_fields = ['customer', 'is_locked']


class WalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WalletTransaction.objects.select_related('wallet')
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsStaffRole]
    filterset_fields = ['wallet', 'transaction_type']
    ordering_fields = ['created_at']


class BettingMarketViewSet(viewsets.ModelViewSet):
    """Future betting platform admin endpoint — gated by IsAdminOrManager until launch."""
    queryset = BettingMarket.objects.select_related('match')
    serializer_class = BettingMarketSerializer
    permission_classes = [IsAdminOrManager]
    filterset_fields = ['status', 'match']

    @action(detail=True, methods=['post'])
    def settle(self, request, pk=None):
        winning_participant_id = request.data.get('winning_participant_id')
        try:
            market = services.settle_betting_market(market_id=pk, winning_participant_id=winning_participant_id)
        except ServiceError as exc:
            return error_response(str(exc))
        return success_response(BettingMarketSerializer(market).data, 'Market settled')


class BetViewSet(viewsets.ModelViewSet):
    queryset = Bet.objects.select_related('market', 'customer', 'predicted_winner')
    serializer_class = BetSerializer
    permission_classes = [IsStaffRole]
    filterset_fields = ['market', 'customer', 'status']

    def create(self, request, *args, **kwargs):
        serializer = PlaceBetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            bet = services.place_bet(**serializer.validated_data)
        except ServiceError as exc:
            return error_response(str(exc))
        return success_response(BetSerializer(bet).data, 'Bet placed', status.HTTP_201_CREATED)


# ===========================================================================
# NOTIFICATIONS, SETTINGS, AUDIT LOGS
# ===========================================================================
class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = NotificationFilter
    ordering_fields = ['created_at']

    def get_queryset(self):
        user = self.request.user
        from django.db.models import Q
        return Notification.objects.filter(Q(recipient=user) | Q(recipient__isnull=True))

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return success_response(NotificationSerializer(notification).data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().update(is_read=True)
        return success_response(message='All notifications marked as read')


class SystemSettingViewSet(viewsets.ModelViewSet):
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    permission_classes = [IsSuperAdmin]
    lookup_field = 'key'


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('actor')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminOrManager]
    filterset_class = AuditLogFilter
    ordering_fields = ['created_at']


# ===========================================================================
# DASHBOARD & REPORTS
# ===========================================================================
class DashboardSummaryView(APIView):
    permission_classes = [IsStaffRole]

    def get(self, request):
        return success_response(services.get_dashboard_summary())


class RevenueReportView(APIView):
    permission_classes = [CanManageFinance]

    def get(self, request):
        period = request.query_params.get('period', 'month')
        start = request.query_params.get('start')
        end = request.query_params.get('end')
        return success_response(services.get_revenue_report(period=period, start=start, end=end))


class ConsoleUtilizationReportView(APIView):
    permission_classes = [CanManageFinance]

    def get(self, request):
        period = request.query_params.get('period', 'today')
        return success_response(list(services.get_console_utilization_report(period=period)))


class BestSellingProductsReportView(APIView):
    permission_classes = [CanManageFinance]

    def get(self, request):
        period = request.query_params.get('period', 'month')
        return success_response(list(services.get_best_selling_products(period=period)))


class MostPlayedGamesReportView(APIView):
    permission_classes = [CanManageFinance]

    def get(self, request):
        period = request.query_params.get('period', 'month')
        return success_response(list(services.get_most_played_games(period=period)))