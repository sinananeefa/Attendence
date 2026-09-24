from django.urls import path
from .views import (
    RecordAttendanceBatchView,
    EnrolledStudentsForAttendanceView,
    AttendanceHistoryListView,
    AttendanceSessionDetailView,
    AttendanceRecordListView,
    AttendanceCorrectionListView,
    AttendanceCorrectionDetailView,
    ApproveAttendanceCorrectionView,
    RejectAttendanceCorrectionView,
    AttendanceAuditLogListView,
    RecordAuditHistoryView,
    StudentMyAttendanceSummaryView,
    SectionAttendanceAnalyticsView,
    AttendancePolicyConfigView,
    LowAttendanceStudentsListView,
    AdminLowAttendanceReportView,
    FacultyLowAttendanceReportView,
    StudentAttendanceWarningsView,
    AdminDashboardOverviewView,
    FacultyDashboardOverviewView,
    StudentDashboardOverviewView,
)


urlpatterns = [
    path('record/', RecordAttendanceBatchView.as_view(), name='record_attendance'),
    path('roster/', EnrolledStudentsForAttendanceView.as_view(), name='attendance_roster'),
    path('history/', AttendanceHistoryListView.as_view(), name='attendance_history'),
    path('sessions/', AttendanceHistoryListView.as_view(), name='session_list'),
    path('sessions/<int:pk>/', AttendanceSessionDetailView.as_view(), name='session_detail'),
    path('records/', AttendanceRecordListView.as_view(), name='record_list'),
    path('records/<int:record_id>/audit-logs/', RecordAuditHistoryView.as_view(), name='record_audit_logs'),
    
    # Phase 7: Attendance Correction Workflow & Audit Trail
    path('corrections/', AttendanceCorrectionListView.as_view(), name='correction_list_create'),
    path('corrections/<int:pk>/', AttendanceCorrectionDetailView.as_view(), name='correction_detail'),
    path('corrections/<int:pk>/approve/', ApproveAttendanceCorrectionView.as_view(), name='correction_approve'),
    path('corrections/<int:pk>/reject/', RejectAttendanceCorrectionView.as_view(), name='correction_reject'),
    path('audit-logs/', AttendanceAuditLogListView.as_view(), name='audit_log_list'),

    path('student/my-summary/', StudentMyAttendanceSummaryView.as_view(), name='student_my_summary'),
    path('analytics/section/<int:section_id>/', SectionAttendanceAnalyticsView.as_view(), name='section_analytics'),
    
    # Phase 6: Low Attendance Detection & Reporting
    path('policy/', AttendancePolicyConfigView.as_view(), name='attendance_policy_config'),
    path('low-attendance/students/', LowAttendanceStudentsListView.as_view(), name='low_attendance_students'),
    path('reports/admin/', AdminLowAttendanceReportView.as_view(), name='admin_low_attendance_report'),
    path('reports/faculty/', FacultyLowAttendanceReportView.as_view(), name='faculty_low_attendance_report'),
    path('student/warnings/', StudentAttendanceWarningsView.as_view(), name='student_attendance_warnings'),

    # Phase 8: Unified Role-Based Dashboards & Reports
    path('dashboard/admin/', AdminDashboardOverviewView.as_view(), name='dashboard_admin'),
    path('dashboard/faculty/', FacultyDashboardOverviewView.as_view(), name='dashboard_faculty'),
    path('dashboard/student/', StudentDashboardOverviewView.as_view(), name='dashboard_student'),
]



