"""
api/signals.py

All Django signal receivers in one module. Primarily drives automatic
audit logging (create/update/delete) for sensitive models, plus small
side-effect hooks (e.g. seeding a Wallet whenever a Customer is created).
"""
from threading import local

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from api.models import (
    User, Customer, Console, GamingSession, Sale, Payment, Expense,
    InventoryItem, Tournament, AuditLog, Wallet,
)

# Thread-local storage so middleware can stash "who made this request" and
# signal handlers can read it without threading request objects everywhere.
_thread_locals = local()


def set_current_actor(user, ip_address=None):
    _thread_locals.user = user
    _thread_locals.ip_address = ip_address


def get_current_actor():
    return getattr(_thread_locals, 'user', None)


def get_current_ip():
    return getattr(_thread_locals, 'ip_address', None)


AUDITED_MODELS = (Customer, Console, GamingSession, Sale, Payment, Expense, InventoryItem, Tournament)


def _write_audit(instance, action):
    actor = get_current_actor()
    AuditLog.objects.create(
        actor=actor if actor and getattr(actor, 'is_authenticated', False) else None,
        action=action,
        model_name=instance.__class__.__name__,
        object_id=str(instance.pk),
        ip_address=get_current_ip(),
    )


@receiver(post_save, sender=Customer)
@receiver(post_save, sender=Console)
@receiver(post_save, sender=GamingSession)
@receiver(post_save, sender=Sale)
@receiver(post_save, sender=Payment)
@receiver(post_save, sender=Expense)
@receiver(post_save, sender=InventoryItem)
@receiver(post_save, sender=Tournament)
def audit_on_save(sender, instance, created, **kwargs):
    _write_audit(instance, AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE)


@receiver(post_delete, sender=Customer)
@receiver(post_delete, sender=Console)
@receiver(post_delete, sender=GamingSession)
@receiver(post_delete, sender=Sale)
@receiver(post_delete, sender=InventoryItem)
@receiver(post_delete, sender=Tournament)
def audit_on_delete(sender, instance, **kwargs):
    _write_audit(instance, AuditLog.Action.DELETE)


@receiver(post_save, sender=Customer)
def create_wallet_for_new_customer(sender, instance, created, **kwargs):
    """Every registered customer gets a wallet, ready for future betting/loyalty use."""
    if created:
        Wallet.objects.get_or_create(customer=instance)


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    AuditLog.objects.create(actor=user, action=AuditLog.Action.LOGIN, model_name='User', object_id=str(user.pk))


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user:
        AuditLog.objects.create(actor=user, action=AuditLog.Action.LOGOUT, model_name='User', object_id=str(user.pk))