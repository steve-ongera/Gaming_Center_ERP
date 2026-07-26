"""
api/urls.py

All API routes for the single `api` app. ViewSets are registered on a
DRF DefaultRouter (giving list/create/retrieve/update/delete + any
@action routes for free); auth, dashboard, and report endpoints are
plain function/class-based paths.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from api import views

router = DefaultRouter()

# Users & customers
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'customers', views.CustomerViewSet, basename='customer')
router.register(r'walk-in-customers', views.WalkInCustomerViewSet, basename='walkincustomer')

# Consoles & games
router.register(r'consoles', views.ConsoleViewSet, basename='console')
router.register(r'games', views.GameViewSet, basename='game')
router.register(r'promotions', views.PromotionViewSet, basename='promotion')

# Sessions & bookings
router.register(r'gaming-sessions', views.GamingSessionViewSet, basename='gamingsession')
router.register(r'bookings', views.BookingViewSet, basename='booking')

# Inventory
router.register(r'inventory-categories', views.InventoryCategoryViewSet, basename='inventorycategory')
router.register(r'suppliers', views.SupplierViewSet, basename='supplier')
router.register(r'inventory-items', views.InventoryItemViewSet, basename='inventoryitem')
router.register(r'stock-movements', views.StockMovementViewSet, basename='stockmovement')

# Sales, payments, expenses
router.register(r'sales', views.SaleViewSet, basename='sale')
router.register(r'payments', views.PaymentViewSet, basename='payment')
router.register(r'expense-categories', views.ExpenseCategoryViewSet, basename='expensecategory')
router.register(r'expenses', views.ExpenseViewSet, basename='expense')

# Tournaments & future betting
router.register(r'tournaments', views.TournamentViewSet, basename='tournament')
router.register(r'tournament-matches', views.TournamentMatchViewSet, basename='tournamentmatch')
router.register(r'wallets', views.WalletViewSet, basename='wallet')
router.register(r'wallet-transactions', views.WalletTransactionViewSet, basename='wallettransaction')
router.register(r'betting-markets', views.BettingMarketViewSet, basename='bettingmarket')
router.register(r'bets', views.BetViewSet, basename='bet')

# Notifications, settings, audit logs
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'settings', views.SystemSettingViewSet, basename='systemsetting')
router.register(r'audit-logs', views.AuditLogViewSet, basename='auditlog')

urlpatterns = [
    # Auth
    path('auth/login/', views.LoginView.as_view(), name='auth-login'),
    path('auth/refresh/', views.RefreshTokenView.as_view(), name='auth-refresh'),
    path('auth/logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', views.MeView.as_view(), name='auth-me'),
    path('auth/change-password/', views.ChangePasswordView.as_view(), name='auth-change-password'),

    # Dashboard & reports
    path('dashboard/summary/', views.DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('reports/revenue/', views.RevenueReportView.as_view(), name='report-revenue'),
    path('reports/console-utilization/', views.ConsoleUtilizationReportView.as_view(), name='report-console-utilization'),
    path('reports/best-selling-products/', views.BestSellingProductsReportView.as_view(), name='report-best-selling'),
    path('reports/most-played-games/', views.MostPlayedGamesReportView.as_view(), name='report-most-played'),

    # Registered viewsets
    path('', include(router.urls)),
]