"""
api/utils.py

Cross-cutting helper functions: standardized API response envelope,
pagination, custom exception handling, receipt/reference number
generation, and small numeric/date helpers used across services.py
and views.py.
"""
import random
import string
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import exception_handler


# ---------------------------------------------------------------------------
# Standardized response envelope
# ---------------------------------------------------------------------------
def api_response(success=True, message='', data=None, errors=None, status_code=status.HTTP_200_OK):
    """
    Every endpoint in this project returns this consistent shape:
        { "success": bool, "message": str, "data": ..., "errors": ... }
    """
    payload = {'success': success, 'message': message, 'data': data, 'errors': errors}
    return Response(payload, status=status_code)


def success_response(data=None, message='Request successful', status_code=status.HTTP_200_OK):
    return api_response(True, message, data, None, status_code)


def error_response(message='Request failed', errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    return api_response(False, message, None, errors, status_code)


def custom_exception_handler(exc, context):
    """Wrap DRF's default exception handler output in the standard envelope."""
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {
            'success': False,
            'message': 'Request failed',
            'data': None,
            'errors': response.data,
        }
    return response


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
class StandardResultsPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response({
            'success': True,
            'message': 'Request successful',
            'data': data,
            'errors': None,
            'pagination': {
                'count': self.page.paginator.count,
                'num_pages': self.page.paginator.num_pages,
                'current_page': self.page.number,
                'page_size': self.get_page_size(self.request),
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
            },
        })


# ---------------------------------------------------------------------------
# Reference / receipt number generation
# ---------------------------------------------------------------------------
def generate_reference(prefix: str, length: int = 8) -> str:
    """e.g. generate_reference('RCPT') -> 'RCPT-20260727-4F9B2C1A'"""
    date_part = timezone.now().strftime('%Y%m%d')
    random_part = uuid.uuid4().hex[:length].upper()
    return f"{prefix}-{date_part}-{random_part}"


def generate_receipt_number() -> str:
    return generate_reference('RCPT')


def generate_payment_reference() -> str:
    return generate_reference('PAY')


def generate_short_code(length: int = 6) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ---------------------------------------------------------------------------
# Numeric / money helpers
# ---------------------------------------------------------------------------
def to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or 0))


def round_money(value: Decimal) -> Decimal:
    return to_decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def minutes_between(start: datetime, end: datetime) -> int:
    delta = end - start
    return max(int(delta.total_seconds() // 60), 0)


# ---------------------------------------------------------------------------
# Date range helpers (used heavily by reports)
# ---------------------------------------------------------------------------
def get_date_range(period: str, start=None, end=None):
    """
    Resolve a named period ('today' | 'week' | 'month' | 'year' | 'custom')
    into a (start_datetime, end_datetime) tuple in the current timezone.
    """
    now = timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == 'today':
        return today_start, now
    if period == 'week':
        return today_start - timezone.timedelta(days=today_start.weekday()), now
    if period == 'month':
        return today_start.replace(day=1), now
    if period == 'year':
        return today_start.replace(month=1, day=1), now
    if period == 'custom' and start and end:
        return start, end
    return today_start, now