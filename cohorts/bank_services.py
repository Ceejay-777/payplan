from django.db import transaction
from django.core.cache import cache
from plans.requests import resolve_bank_account as nomba_resolve
from .models import SavedBankAccount


def save_bank_account(user, account_number, bank_code, nickname=None, is_default=False):
    account_name = nomba_resolve(account_number, bank_code)
    bank_name = ''

    with transaction.atomic():
        if is_default:
            SavedBankAccount.objects.filter(user=user, is_default=True).update(is_default=False)

        account = SavedBankAccount.objects.create(
            user=user,
            account_name=account_name,
            account_number=account_number,
            bank_code=bank_code,
            bank_name=bank_name,
            nickname=nickname or '',
            is_default=is_default,
        )

    return account


def update_bank_account(account, validated_data):
    if validated_data.get('is_default'):
        SavedBankAccount.objects.filter(user=account.user, is_default=True).exclude(pk=account.pk).update(is_default=False)

    for attr, value in validated_data.items():
        setattr(account, attr, value)
    account.save(update_fields=validated_data.keys())
    account.refresh_from_db()
    return account


def delete_bank_account(account):
    account.status = SavedBankAccount.Status.INACTIVE
    account.save(update_fields=['status'])


def resolve_bank_account(account_number, bank_code):
    cache_key = f"bank_resolve_{account_number}_{bank_code}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    account_name = nomba_resolve(account_number, bank_code)
    cache.set(cache_key, account_name, 300)
    return account_name
