"""
api/middleware.py

Lightweight middleware that stashes the requesting user and IP address in
thread-local storage so api/signals.py can attribute audit log entries
without every service function needing an explicit `actor` parameter for
signal-driven (as opposed to explicit) audit writes.
"""
from api.signals import set_current_actor


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        set_current_actor(user, get_client_ip(request))
        response = self.get_response(request)
        return response