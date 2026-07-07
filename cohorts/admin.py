from django.contrib import admin

from .models import Cohort, CohortMembership, SavedBankAccount

@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ['name', 'organizer', 'frequency', 'visibility', 'created_at']
    search_fields = ['name', 'organizer__email']
    list_filter = ['frequency', 'visibility']
    raw_id_fields = ['organizer']

@admin.register(CohortMembership)
class CohortMembershipAdmin(admin.ModelAdmin):
    list_display = ['cohort', 'plan', 'amount', 'status', 'joined_at']
    list_filter = ['status']
    raw_id_fields = ['cohort', 'plan']

@admin.register(SavedBankAccount)
class SavedBankAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'account_name', 'account_number', 'bank_code', 'is_default', 'status']
    list_filter = ['status', 'is_default']
    search_fields = ['account_name', 'account_number', 'user__email']
