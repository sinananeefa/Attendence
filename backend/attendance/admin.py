from django.contrib import admin
from .models import (
    AttendanceSession, AttendanceRecord, AttendanceCorrection, AttendanceAuditLog, AttendancePolicy
)


class AttendanceRecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0
    fields = ('student', 'status', 'remarks', 'marked_at')
    readonly_fields = ('marked_at',)
    can_delete = False


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'session_date', 'period_number', 'section', 'subject',
        'faculty', 'session_type', 'status', 'is_locked', 'get_summary'
    )
    list_filter = ('session_date', 'period_number', 'session_type', 'status', 'is_locked', 'section__program__department')
    search_fields = ('subject__code', 'subject__title', 'section__name', 'faculty__first_name', 'faculty__last_name', 'topic_covered')
    date_hierarchy = 'session_date'
    inlines = [AttendanceRecordInline]

    def get_summary(self, obj):
        return f"{obj.present_count}/{obj.total_students} Present ({obj.attendance_percentage}%)"
    get_summary.short_description = 'Attendance'


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'session', 'status', 'remarks', 'marked_at')
    list_filter = ('status', 'marked_at', 'session__session_date', 'session__subject')
    search_fields = ('student__roll_number', 'student__user__first_name', 'student__user__last_name', 'session__subject__code')


@admin.register(AttendanceCorrection)
class AttendanceCorrectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'record', 'old_status', 'requested_status', 'status', 'requested_by', 'reviewed_by', 'created_at')
    list_filter = ('status', 'old_status', 'requested_status', 'created_at')
    search_fields = ('record__student__roll_number', 'requested_by__username', 'reason')


@admin.register(AttendanceAuditLog)
class AttendanceAuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'record', 'action', 'previous_status', 'new_status', 'changed_by', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('record__student__roll_number', 'changed_by__username', 'reason')
    readonly_fields = ('record', 'action', 'previous_status', 'new_status', 'changed_by', 'reason', 'ip_address', 'timestamp')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AttendancePolicy)
class AttendancePolicyAdmin(admin.ModelAdmin):
    list_display = ('institution_name', 'default_threshold', 'condonation_threshold', 'warning_buffer_pct', 'is_active', 'updated_at', 'updated_by')
    list_filter = ('is_active', 'updated_at')
    search_fields = ('institution_name',)

