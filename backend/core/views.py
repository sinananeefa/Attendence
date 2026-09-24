from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.models import Role, User
from academic.models import Department, Program, Section, Subject, Student, Faculty
from attendance.models import (
    AttendanceSession, AttendanceRecord, AttendanceCorrection, AttendanceAuditLog,
    AttendanceStatus, SessionStatus, CorrectionStatus
)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    System status and database connectivity health check.
    """
    db_ok = True
    try:
        connection.ensure_connection()
    except Exception as e:
        db_ok = False

    return Response({
        'status': 'healthy' if db_ok else 'degraded',
        'database_connected': db_ok,
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0-phase1',
        'service': 'Smart Attendance Management API (Edumerge Assignment 1)'
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def system_overview(request):
    """
    Overview of database entities, counts, and architectural enum schemas.
    Allows frontend to inspect active schema directly.
    """
    return Response({
        'architecture_phase': 'Phase 1 - Project Architecture and Database Design',
        'stats': {
            'users_count': User.objects.count(),
            'departments_count': Department.objects.count(),
            'programs_count': Program.objects.count(),
            'sections_count': Section.objects.count(),
            'subjects_count': Subject.objects.count(),
            'students_count': Student.objects.count(),
            'faculty_count': Faculty.objects.count(),
            'attendance_sessions_count': AttendanceSession.objects.count(),
            'attendance_records_count': AttendanceRecord.objects.count(),
            'corrections_count': AttendanceCorrection.objects.count(),
            'audit_logs_count': AttendanceAuditLog.objects.count(),
        },
        'enums': {
            'roles': [{'code': k, 'label': v} for k, v in Role.choices],
            'attendance_statuses': [{'code': k, 'label': v} for k, v in AttendanceStatus.choices],
            'session_statuses': [{'code': k, 'label': v} for k, v in SessionStatus.choices],
            'correction_statuses': [{'code': k, 'label': v} for k, v in CorrectionStatus.choices],
        },
        'statutory_rules': {
            'statutory_min_attendance_pct': 75.0,
            'condonation_min_pct': 65.0,
            'debarment_threshold_pct': 65.0,
            'session_edit_grace_hours': 24,
        }
    })
