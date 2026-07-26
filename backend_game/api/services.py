"""
api/services.py

Service-layer business logic. Views should stay thin and delegate all
non-trivial work to functions here, wrapped in atomic transactions where
multiple models are touched. This keeps business rules centralized,
testable, and reusable across the REST API, admin actions, and management
commands / Celery tasks.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Count, Q, F
from django.utils import timezone

from api.models import (
    Console, Game, GamingSession, Customer, WalkInCustomer, Booking,
    InventoryItem, StockMovement, Sale, SaleItem, Payment, Expense,
    Tournament, TournamentParticipant, TournamentMatch, BettingMarket, Bet,
    Wallet, WalletTransaction, Notification, Promotion, AuditLog,
)
from api.utils import (
    to_decimal, round_money, minutes_between, generate_receipt_number,
    generate_payment_reference, get_date_range,
)


class ServiceError(Exception):
    """Raised for business-rule violations; views translate this into a 400."""


# ===========================================================================
# GAMING SESSIONS
# ===========================================================================
@transaction.atomic
def start_gaming_session(*, console_id, started_by, game_id=None, customer_id=None,
                          walk_in_name=None, walk_in_phone=None, number_of_players=1,
                          planned_duration_minutes=None, promotion_code=None):
    """
    Start a new gaming session on a console. Walk-ins need no registration —
    a lightweight WalkInCustomer row is created automatically unless an
    existing registered customer_id is supplied.
    """
    console = Console.objects.select_for_update().get(id=console_id)

    if console.status == Console.Status.MAINTENANCE:
        raise ServiceError('This console is under maintenance and cannot be assigned.')
    if not console.is_assignable():
        raise ServiceError('This console is not available for a new session.')

    active_exists = GamingSession.objects.filter(
        console=console, status__in=[GamingSession.Status.ACTIVE, GamingSession.Status.PAUSED]
    ).exists()
    if active_exists:
        raise ServiceError('This console already has an active session.')

    customer = None
    walk_in_customer = None
    if customer_id:
        customer = Customer.objects.get(id=customer_id)
    else:
        walk_in_customer = WalkInCustomer.objects.create(
            name=walk_in_name or 'Guest', phone_number=walk_in_phone or ''
        )

    promotion = None
    if promotion_code:
        promotion = Promotion.objects.filter(code=promotion_code).first()
        if not promotion or not promotion.is_valid_now():
            raise ServiceError('Promotion code is invalid or expired.')

    session = GamingSession.objects.create(
        console=console,
        game_id=game_id,
        customer=customer,
        walk_in_customer=walk_in_customer,
        started_by=started_by,
        number_of_players=number_of_players,
        hourly_rate_snapshot=console.hourly_rate,
        planned_duration_minutes=planned_duration_minutes,
        promotion=promotion,
        start_time=timezone.now(),
    )

    console.status = Console.Status.OCCUPIED
    console.save(update_fields=['status'])

    if game_id:
        Game.objects.filter(id=game_id).update(times_played=F('times_played') + 1)

    notify(
        notification_type=Notification.NotificationType.SESSION_STARTED,
        title='Gaming session started',
        message=f'Session started on {console.console_number}.',
        link='/portal/gaming-sessions',
    )
    return session


def calculate_session_charges(session: GamingSession, end_time=None):
    """
    Pure calculation (no DB writes): hourly rate * duration + extra time,
    minus discounts/promotions. Returns a dict suitable for both preview
    (while active) and finalization (on stop).
    """
    end_time = end_time or timezone.now()
    total_minutes = minutes_between(session.start_time, end_time) + session.extra_minutes
    hours = Decimal(total_minutes) / Decimal(60)
    subtotal = round_money(to_decimal(session.hourly_rate_snapshot) * hours)

    discount = to_decimal(session.discount_amount)
    if session.promotion and session.promotion.is_valid_now():
        promo = session.promotion
        if promo.discount_type == Promotion.DiscountType.PERCENTAGE:
            discount = round_money(subtotal * (to_decimal(promo.value) / Decimal(100)))
        else:
            discount = to_decimal(promo.value)

    total = max(round_money(subtotal - discount), Decimal('0.00'))
    return {
        'total_minutes': total_minutes,
        'subtotal_amount': subtotal,
        'discount_amount': discount,
        'total_amount': total,
    }


@transaction.atomic
def stop_gaming_session(*, session_id, closed_by):
    session = GamingSession.objects.select_for_update().select_related('console').get(id=session_id)
    if session.status not in (GamingSession.Status.ACTIVE, GamingSession.Status.PAUSED):
        raise ServiceError('Session is not active.')

    charges = calculate_session_charges(session)
    session.end_time = timezone.now()
    session.subtotal_amount = charges['subtotal_amount']
    session.discount_amount = charges['discount_amount']
    session.total_amount = charges['total_amount']
    session.status = GamingSession.Status.COMPLETED
    session.closed_by = closed_by
    session.save()

    console = session.console
    console.status = Console.Status.AVAILABLE
    console.save(update_fields=['status'])

    if session.promotion:
        Promotion.objects.filter(id=session.promotion_id).update(times_used=F('times_used') + 1)

    notify(
        notification_type=Notification.NotificationType.SESSION_COMPLETED,
        title='Gaming session completed',
        message=f'Session on {console.console_number} totalled {session.total_amount}.',
        link='/portal/gaming-sessions',
    )
    return session


# ===========================================================================
# CUSTOMERS
# ===========================================================================
@transaction.atomic
def convert_walkin_to_customer(*, walk_in_customer_id, phone_number, first_name, last_name=''):
    walk_in = WalkInCustomer.objects.select_for_update().get(id=walk_in_customer_id)
    if walk_in.is_converted:
        raise ServiceError('This walk-in has already been converted.')

    customer, created = Customer.objects.get_or_create(
        phone_number=phone_number,
        defaults={'first_name': first_name, 'last_name': last_name, 'converted_from_walkin': walk_in},
    )
    walk_in.is_converted = True
    walk_in.save(update_fields=['is_converted'])

    # Re-point historical sessions/sales to the new registered customer.
    GamingSession.objects.filter(walk_in_customer=walk_in).update(customer=customer)
    Sale.objects.filter(walk_in_customer=walk_in).update(customer=customer)

    Wallet.objects.get_or_create(customer=customer)
    return customer


# ===========================================================================
# INVENTORY & SALES
# ===========================================================================
@transaction.atomic
def adjust_stock(*, item_id, quantity_change, movement_type, performed_by, reference_note=''):
    item = InventoryItem.objects.select_for_update().get(id=item_id)
    new_quantity = item.stock_quantity + quantity_change
    if new_quantity < 0:
        raise ServiceError(f'Insufficient stock for {item.name}.')

    item.stock_quantity = new_quantity
    item.save(update_fields=['stock_quantity'])

    StockMovement.objects.create(
        item=item, movement_type=movement_type, quantity_change=quantity_change,
        resulting_quantity=new_quantity, performed_by=performed_by, reference_note=reference_note,
    )

    if item.is_low_stock:
        notify(
            notification_type=Notification.NotificationType.LOW_STOCK,
            title='Low stock alert',
            message=f'{item.name} is at {new_quantity} units (reorder level {item.reorder_level}).',
            link='/portal/inventory',
        )
    return item


@transaction.atomic
def create_sale(*, sold_by, line_items, customer_id=None, walk_in_customer_id=None,
                 gaming_session_id=None, discount_amount=Decimal('0.00')):
    """
    line_items: list of {"item_id": ..., "quantity": ...}
    Automatically reduces stock and produces a receipt-ready Sale.
    """
    if not line_items:
        raise ServiceError('A sale requires at least one line item.')

    sale = Sale.objects.create(
        receipt_number=generate_receipt_number(),
        sold_by=sold_by,
        customer_id=customer_id,
        walk_in_customer_id=walk_in_customer_id,
        gaming_session_id=gaming_session_id,
        discount_amount=discount_amount,
    )

    subtotal = Decimal('0.00')
    for line in line_items:
        item = InventoryItem.objects.select_for_update().get(id=line['item_id'])
        quantity = int(line['quantity'])
        if item.stock_quantity < quantity:
            raise ServiceError(f'Not enough stock for {item.name}.')

        line_total = round_money(to_decimal(item.selling_price) * quantity)
        SaleItem.objects.create(sale=sale, item=item, quantity=quantity, unit_price=item.selling_price, line_total=line_total)
        subtotal += line_total

        adjust_stock(
            item_id=item.id, quantity_change=-quantity, movement_type=StockMovement.MovementType.SALE,
            performed_by=sold_by, reference_note=f'Sale {sale.receipt_number}',
        )

    total = max(round_money(subtotal - to_decimal(discount_amount)), Decimal('0.00'))
    sale.subtotal_amount = subtotal
    sale.total_amount = total
    sale.save(update_fields=['subtotal_amount', 'total_amount'])

    if customer_id:
        Customer.objects.filter(id=customer_id).update(total_spent=F('total_spent') + total)

    return sale


# ===========================================================================
# PAYMENTS
# ===========================================================================
@transaction.atomic
def record_payment(*, method, amount, received_by, gaming_session_id=None, sale_id=None,
                    booking_id=None, customer_id=None, meta=None):
    payment = Payment.objects.create(
        reference_code=generate_payment_reference(),
        method=method,
        amount=amount,
        status=Payment.Status.SUCCESSFUL,
        gaming_session_id=gaming_session_id,
        sale_id=sale_id,
        booking_id=booking_id,
        customer_id=customer_id,
        received_by=received_by,
        meta=meta or {},
    )

    if gaming_session_id:
        GamingSession.objects.filter(id=gaming_session_id).update(is_paid=True)
    if booking_id:
        Booking.objects.filter(id=booking_id).update(deposit_paid=True)

    notify(
        notification_type=Notification.NotificationType.PAYMENT_RECEIVED,
        title='Payment received',
        message=f'{payment.get_method_display()} payment of {amount} recorded.',
        link='/portal/payments',
    )
    return payment


# ===========================================================================
# TOURNAMENTS & FUTURE BETTING PLATFORM
# ===========================================================================
@transaction.atomic
def register_tournament_participant(*, tournament_id, customer_id):
    tournament = Tournament.objects.select_for_update().get(id=tournament_id)
    current_count = tournament.participants.count()
    if current_count >= tournament.max_participants:
        raise ServiceError('Tournament is full.')

    participant, created = TournamentParticipant.objects.get_or_create(
        tournament=tournament, customer_id=customer_id, defaults={'seed_number': current_count + 1}
    )
    if not created:
        raise ServiceError('Customer already registered for this tournament.')

    notify(
        notification_type=Notification.NotificationType.TOURNAMENT_CREATED,
        title='New tournament participant',
        message=f'{participant.customer} joined {tournament.name}.',
        link='/portal/betting',
    )
    return participant


@transaction.atomic
def place_bet(*, market_id, customer_id, predicted_winner_id, stake_amount):
    """
    Future betting platform: deducts stake from the customer's wallet and
    opens a Bet against a BettingMarket. Disabled at the view layer until
    the feature flag is turned on, but fully modeled here already.
    """
    market = BettingMarket.objects.select_for_update().get(id=market_id)
    if market.status != BettingMarket.Status.OPEN:
        raise ServiceError('This betting market is not open.')

    wallet = Wallet.objects.select_for_update().get(customer_id=customer_id)
    stake = to_decimal(stake_amount)
    if wallet.is_locked or wallet.balance < stake:
        raise ServiceError('Insufficient wallet balance.')

    odds = market.odds_player_one if str(market.match.player_one_id) == str(predicted_winner_id) else market.odds_player_two

    wallet.balance -= stake
    wallet.save(update_fields=['balance'])
    wallet_tx = WalletTransaction.objects.create(
        wallet=wallet, transaction_type=WalletTransaction.TransactionType.BET_PLACED,
        amount=-stake, balance_after=wallet.balance, reference=str(market.id),
    )

    bet = Bet.objects.create(
        market=market, customer_id=customer_id, predicted_winner_id=predicted_winner_id,
        stake_amount=stake, odds_at_placement=odds, potential_payout=round_money(stake * odds),
        wallet_transaction=wallet_tx,
    )
    return bet


@transaction.atomic
def settle_betting_market(*, market_id, winning_participant_id):
    market = BettingMarket.objects.select_for_update().get(id=market_id)
    market.status = BettingMarket.Status.SETTLED
    market.winning_outcome_id = winning_participant_id
    market.settled_at = timezone.now()
    market.save(update_fields=['status', 'winning_outcome_id', 'settled_at'])

    for bet in market.bets.select_related('customer__wallet').filter(status=Bet.Status.PLACED):
        won = str(bet.predicted_winner_id) == str(winning_participant_id)
        bet.status = Bet.Status.WON if won else Bet.Status.LOST
        bet.settled_at = timezone.now()
        bet.save(update_fields=['status', 'settled_at'])

        if won:
            wallet = bet.customer.wallet
            wallet.balance += bet.potential_payout
            wallet.save(update_fields=['balance'])
            WalletTransaction.objects.create(
                wallet=wallet, transaction_type=WalletTransaction.TransactionType.BET_PAYOUT,
                amount=bet.potential_payout, balance_after=wallet.balance, reference=str(market.id),
            )
    return market


# ===========================================================================
# NOTIFICATIONS
# ===========================================================================
def notify(*, notification_type, title, message, recipient=None, link=''):
    return Notification.objects.create(
        recipient=recipient, notification_type=notification_type, title=title, message=message, link=link,
    )


# ===========================================================================
# DASHBOARD & REPORTS
# ===========================================================================
def get_dashboard_summary():
    start, end = get_date_range('today')

    today_sessions = GamingSession.objects.filter(start_time__gte=start, start_time__lte=end)
    today_sales = Sale.objects.filter(created_at__gte=start, created_at__lte=end, status=Sale.Status.COMPLETED)
    today_expenses = Expense.objects.filter(incurred_on=timezone.localdate())

    session_revenue = today_sessions.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    sales_revenue = today_sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_revenue = session_revenue + sales_revenue
    total_expenses = today_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    consoles = Console.objects.all()
    low_stock_count = InventoryItem.objects.filter(stock_quantity__lte=F('reorder_level')).count()

    return {
        'today_revenue': total_revenue,
        'today_profit': total_revenue - total_expenses,
        'today_expenses': total_expenses,
        'active_sessions': GamingSession.objects.filter(
            status__in=[GamingSession.Status.ACTIVE, GamingSession.Status.PAUSED]
        ).count(),
        'available_consoles': consoles.filter(status=Console.Status.AVAILABLE).count(),
        'occupied_consoles': consoles.filter(status=Console.Status.OCCUPIED).count(),
        'games_played_today': today_sessions.exclude(game__isnull=True).values('game').distinct().count(),
        'walk_in_customers_today': today_sessions.filter(customer__isnull=True).values('walk_in_customer').distinct().count(),
        'registered_customers': Customer.objects.count(),
        'pending_payments': Payment.objects.filter(status=Payment.Status.PENDING).count(),
        'low_stock_alerts': low_stock_count,
        'tournaments_ongoing': Tournament.objects.filter(status=Tournament.Status.ONGOING).count(),
        'tournaments_upcoming': Tournament.objects.filter(status=Tournament.Status.UPCOMING).count(),
    }


def get_revenue_report(*, period='month', start=None, end=None):
    range_start, range_end = get_date_range(period, start, end)

    sessions = GamingSession.objects.filter(
        start_time__gte=range_start, start_time__lte=range_end, status=GamingSession.Status.COMPLETED
    )
    sales = Sale.objects.filter(created_at__gte=range_start, created_at__lte=range_end, status=Sale.Status.COMPLETED)
    expenses = Expense.objects.filter(incurred_on__gte=range_start.date(), incurred_on__lte=range_end.date())

    session_revenue = sessions.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    sales_revenue = sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_revenue = session_revenue + sales_revenue

    return {
        'period': period,
        'range_start': range_start,
        'range_end': range_end,
        'session_revenue': session_revenue,
        'sales_revenue': sales_revenue,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'net_profit': total_revenue - total_expenses,
        'session_count': sessions.count(),
        'sale_count': sales.count(),
    }


def get_console_utilization_report(*, period='today'):
    start, end = get_date_range(period)
    return (
        Console.objects.annotate(
            session_count=Count('sessions', filter=Q(sessions__start_time__gte=start, sessions__start_time__lte=end)),
            revenue=Sum('sessions__total_amount', filter=Q(sessions__start_time__gte=start, sessions__start_time__lte=end)),
        ).values('id', 'console_number', 'console_type', 'session_count', 'revenue')
    )


def get_best_selling_products(*, period='month', limit=10):
    start, end = get_date_range(period)
    return (
        SaleItem.objects.filter(sale__created_at__gte=start, sale__created_at__lte=end, sale__status=Sale.Status.COMPLETED)
        .values('item__id', 'item__name')
        .annotate(total_quantity=Sum('quantity'), total_revenue=Sum('line_total'))
        .order_by('-total_quantity')[:limit]
    )


def get_most_played_games(*, period='month', limit=10):
    start, end = get_date_range(period)
    return (
        GamingSession.objects.filter(start_time__gte=start, start_time__lte=end, game__isnull=False)
        .values('game__id', 'game__title')
        .annotate(play_count=Count('id'))
        .order_by('-play_count')[:limit]
    )