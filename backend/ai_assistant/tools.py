"""
Deterministic Backend Tools for AI Attendance Assistant.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. All functions are strictly READ-ONLY. No mutation or deletion of database state is permitted.
2. The LLM must NEVER calculate or recalculate attendance percentages. All percentages,
   threshold comparisons, and recovery projections are computed deterministically by
   AttendanceCalculationService.
3. No arbitrary or user-generated SQL is accepted or executed.
4. If data is unavailable, functions return clean, structured responses stating that explicitly.
"""

from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count

from academic.models import Student, Subject, Department, AcademicClass, Section
from attendance.models import AttendanceSession, AttendanceRecord, AttendanceStatus
from attendance.services import (
    AttendanceCalculationService,
    calculate_attendance_percentage,
    get_effective_threshold
)

ATTENDED_STATUSES = [
    AttendanceStatus.PRESENT,
    AttendanceStatus.LATE,
    AttendanceStatus.ON_DUTY,
    AttendanceStatus.MEDICAL_LEAVE
]


def get_student_attendance(student_identifier: str, threshold: Optional[float] = None) -> Dict[str, Any]:
    """
    Retrieves full deterministic attendance records and calculations for a student.
    
    Args:
        student_identifier: Student roll number, username, or full/first name (e.g., '24CSE001', 'Rahul').
        threshold: Optional custom statutory threshold (defaults to institutional policy of 75.0%).
        
    Returns:
        Structured dictionary containing overall attendance, subject breakdown, and status.
    """
    if not student_identifier or not str(student_identifier).strip():
        return {
            'status': 'error',
            'found': False,
            'message': "No student identifier provided. Please provide a roll number, username, or name."
        }

    identifier = str(student_identifier).strip()

    # Search by exact roll number, then username, then first/last name
    student_query = Student.objects.select_related(
        'user', 'section__academic_class__program__department'
    ).filter(user__is_active=True)

    # 1. Exact match by roll number (case-insensitive)
    matched_student = student_query.filter(roll_number__iexact=identifier).first()

    # 2. Match by username (case-insensitive)
    if not matched_student:
        matched_student = student_query.filter(user__username__iexact=identifier).first()

    # 3. Match by first name or full name (case-insensitive)
    if not matched_student:
        candidates = list(student_query.filter(
            Q(user__first_name__iexact=identifier) |
            Q(user__last_name__iexact=identifier) |
            Q(user__first_name__icontains=identifier)
        ))
        if len(candidates) == 1:
            matched_student = candidates[0]
        elif len(candidates) > 1:
            # Ambiguous: list the matching candidates
            return {
                'status': 'ambiguous',
                'found': True,
                'multiple_matches': True,
                'message': f"Multiple students found matching '{identifier}'. Please specify the roll number.",
                'candidates': [
                    {
                        'roll_number': c.roll_number,
                        'name': c.user.get_full_name() or c.user.username,
                        'department': c.section.academic_class.program.department.code if c.section else 'N/A',
                        'section': c.section.name if c.section else 'N/A',
                    }
                    for c in candidates
                ]
            }

    if not matched_student:
        return {
            'status': 'not_found',
            'found': False,
            'message': f"Student '{identifier}' was not found in active university records."
        }

    # Convert threshold to Decimal safely
    thresh_dec = None
    if threshold is not None:
        try:
            thresh_dec = Decimal(str(threshold))
        except Exception:
            thresh_dec = None

    # Calculate overall attendance using deterministic calculation service
    overall_summary = AttendanceCalculationService.calculate_student_overall_attendance(
        matched_student, threshold=thresh_dec
    )

    # Subject-wise attendance calculation
    enrollments = matched_student.course_enrollments.filter(is_active=True).select_related('subject')
    subjects_data = []

    for enr in enrollments:
        subj = enr.subject
        sub_calc = AttendanceCalculationService.calculate_student_subject_attendance(
            matched_student, subj, threshold=thresh_dec
        )
        subjects_data.append(sub_calc)

    department_name = (
        matched_student.section.academic_class.program.department.name
        if matched_student.section and matched_student.section.academic_class and matched_student.section.academic_class.program
        else 'Unassigned'
    )
    section_name = matched_student.section.name if matched_student.section else 'Unassigned'

    return {
        'status': 'success',
        'found': True,
        'student': {
            'roll_number': matched_student.roll_number,
            'full_name': matched_student.user.get_full_name() or matched_student.user.username,
            'username': matched_student.user.username,
            'department': department_name,
            'section': section_name,
            'semester': matched_student.current_semester,
        },
        'threshold_used': float(overall_summary['threshold_used']),
        'overall_attendance': {
            'overall_percentage': float(overall_summary['overall_percentage']),
            'total_conducted': overall_summary['total_conducted'],
            'total_attended': overall_summary['total_attended'],
            'total_missed': overall_summary['total_missed'],
            'is_low_attendance': overall_summary['is_low_attendance'],
            'classes_needed_for_target': overall_summary['classes_needed_for_target'],
            'classes_can_miss_for_target': overall_summary['classes_can_miss_for_target'],
            'overall_status': overall_summary['overall_status'],
        },
        'subjects': subjects_data,
        'has_conducted_classes': overall_summary['total_conducted'] > 0
    }


def get_low_attendance_students(threshold: float = 75.0, department_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Identifies all students falling strictly below the given attendance threshold.
    
    Args:
        threshold: The percentage boundary (e.g. 75.0, 70.0). Defaults to 75.0%.
        department_code: Optional department filter (e.g. 'CSE', 'ECE').
        
    Returns:
        Structured list of at-risk students with deficit percentages and recovery targets.
    """
    try:
        thresh_dec = Decimal(str(threshold))
    except Exception:
        thresh_dec = Decimal('75.00')

    students_qs = Student.objects.filter(user__is_active=True).select_related(
        'user', 'section__academic_class__program__department'
    )

    if department_code:
        dept_clean = str(department_code).strip().upper()
        students_qs = students_qs.filter(section__academic_class__program__department__code=dept_clean)

    low_attendance_students = []
    total_evaluated = 0

    for st in students_qs:
        total_evaluated += 1
        summary = AttendanceCalculationService.calculate_student_overall_attendance(st, threshold=thresh_dec)
        
        # Only flag if classes were conducted and attendance percentage is strictly below threshold
        if summary['total_conducted'] > 0 and summary['is_low_attendance']:
            dept_code = st.section.academic_class.program.department.code if st.section and st.section.academic_class and st.section.academic_class.program else 'N/A'
            dept_name = st.section.academic_class.program.department.name if st.section and st.section.academic_class and st.section.academic_class.program else 'N/A'
            sec_name = st.section.name if st.section else 'N/A'

            low_attendance_students.append({
                'roll_number': st.roll_number,
                'name': st.user.get_full_name() or st.user.username,
                'department_code': dept_code,
                'department_name': dept_name,
                'section': sec_name,
                'overall_percentage': float(summary['overall_percentage']),
                'total_conducted': summary['total_conducted'],
                'total_attended': summary['total_attended'],
                'total_missed': summary['total_missed'],
                'classes_needed_to_reach_threshold': summary['classes_needed_for_target'],
                'status': summary['overall_status'],
            })

    # Sort descending by deficit (lowest attendance first)
    low_attendance_students.sort(key=lambda s: s['overall_percentage'])

    return {
        'status': 'success',
        'threshold_used': float(thresh_dec),
        'department_filter': department_code,
        'total_students_evaluated': total_evaluated,
        'low_attendance_count': len(low_attendance_students),
        'students': low_attendance_students,
        'is_empty': len(low_attendance_students) == 0,
        'message': (
            f"Found {len(low_attendance_students)} student(s) below {float(thresh_dec)}% attendance."
            if low_attendance_students
            else f"No students are below the {float(thresh_dec)}% threshold."
        )
    }


def get_subject_attendance(subject_code: Optional[str] = None, department_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes cohort attendance metrics across subjects, ranking from lowest to highest.
    
    Args:
        subject_code: Optional specific subject code (e.g. 'CS401').
        department_code: Optional department filter (e.g. 'CSE').
        
    Returns:
        Structured list of subjects with conducted sessions, attended records, average %,
        and explicit identification of the lowest and highest attendance courses.
    """
    subjects_qs = Subject.objects.all().select_related('department')

    if subject_code:
        code_clean = str(subject_code).strip().upper()
        subjects_qs = subjects_qs.filter(code=code_clean)
        if not subjects_qs.exists():
            return {
                'status': 'not_found',
                'found': False,
                'message': f"Subject with code '{code_clean}' was not found in university courses."
            }

    if department_code:
        dept_clean = str(department_code).strip().upper()
        subjects_qs = subjects_qs.filter(department__code=dept_clean)

    subject_results = []

    for subj in subjects_qs:
        sessions = AttendanceSession.objects.filter(subject=subj)
        session_ids = sessions.values_list('id', flat=True)
        total_sessions = sessions.count()

        records = AttendanceRecord.objects.filter(session_id__in=session_ids)
        total_records = records.count()
        attended_count = records.filter(status__in=ATTENDED_STATUSES).count()

        pct = calculate_attendance_percentage(attended_count, total_records)

        subject_results.append({
            'code': subj.code,
            'title': subj.title,
            'department_code': subj.department.code,
            'department_name': subj.department.name,
            'credits': subj.credits,
            'semester': subj.semester,
            'total_sessions_conducted': total_sessions,
            'total_records_evaluated': total_records,
            'total_attended': attended_count,
            'average_attendance_percentage': float(pct),
            'has_classes': total_records > 0
        })

    # Sort from lowest attendance percentage to highest (prioritize subjects with conducted classes)
    active_subjects = [s for s in subject_results if s['has_classes']]
    inactive_subjects = [s for s in subject_results if not s['has_classes']]

    active_subjects.sort(key=lambda s: s['average_attendance_percentage'])

    lowest_subject = active_subjects[0] if active_subjects else None
    highest_subject = active_subjects[-1] if active_subjects else None

    return {
        'status': 'success',
        'found': True,
        'total_subjects_analyzed': len(subject_results),
        'active_subjects_count': len(active_subjects),
        'lowest_attendance_subject': lowest_subject,
        'highest_attendance_subject': highest_subject,
        'subjects': active_subjects + inactive_subjects,
        'message': (
            f"The subject with lowest attendance is {lowest_subject['code']} ({lowest_subject['title']}) at {lowest_subject['average_attendance_percentage']}%."
            if lowest_subject
            else "No subjects currently have recorded attendance sessions."
        )
    }


def get_department_attendance() -> Dict[str, Any]:
    """
    Computes aggregated attendance performance across all university departments.
    
    Returns:
        Structured breakdown comparing all departments, identifying the lowest and highest.
    """
    departments = Department.objects.all()
    dept_results = []

    for dept in departments:
        # Get all sessions belonging to sections in this department
        sessions = AttendanceSession.objects.filter(section__program__department=dept)
        session_ids = sessions.values_list('id', flat=True)
        total_sessions = sessions.count()

        records = AttendanceRecord.objects.filter(session_id__in=session_ids)
        total_records = records.count()
        attended_count = records.filter(status__in=ATTENDED_STATUSES).count()

        pct = calculate_attendance_percentage(attended_count, total_records)
        total_students = Student.objects.filter(section__academic_class__program__department=dept, user__is_active=True).count()
        total_faculty = dept.faculty_members.filter(user__is_active=True).count()

        dept_results.append({
            'department_code': dept.code,
            'department_name': dept.name,
            'total_students': total_students,
            'total_faculty': total_faculty,
            'total_sessions_conducted': total_sessions,
            'total_records_evaluated': total_records,
            'total_attended': attended_count,
            'attendance_percentage': float(pct),
            'has_classes': total_records > 0
        })

    active_depts = [d for d in dept_results if d['has_classes']]
    inactive_depts = [d for d in dept_results if not d['has_classes']]

    # Sort from lowest attendance percentage to highest
    active_depts.sort(key=lambda d: d['attendance_percentage'])

    lowest_dept = active_depts[0] if active_depts else None
    highest_dept = active_depts[-1] if active_depts else None

    return {
        'status': 'success',
        'total_departments': len(dept_results),
        'active_departments_count': len(active_depts),
        'lowest_attendance_department': lowest_dept,
        'highest_attendance_department': highest_dept,
        'departments': active_depts + inactive_depts,
        'message': (
            f"The department with the lowest attendance is {lowest_dept['department_name']} ({lowest_dept['department_code']}) at {lowest_dept['attendance_percentage']}%."
            if lowest_dept
            else "No departmental attendance sessions have been conducted yet."
        )
    }


def get_attendance_history(
    student_identifier: Optional[str] = None,
    subject_code: Optional[str] = None,
    days: int = 30
) -> Dict[str, Any]:
    """
    Retrieves chronological attendance log entries for a student or subject within a time window.
    
    Args:
        student_identifier: Optional roll number or username to filter by.
        subject_code: Optional subject code (e.g. 'CS401').
        days: Historical window in days (default 30 days).
        
    Returns:
        Structured list of individual attendance session records.
    """
    now = timezone.localdate()
    start_date = now - timedelta(days=days)

    records_qs = AttendanceRecord.objects.filter(
        session__session_date__gte=start_date,
        session__session_date__lte=now
    ).select_related(
        'student__user',
        'session__subject',
        'session__section',
        'session__faculty'
    ).order_by('-session__session_date', '-session__period_number')

    if student_identifier:
        ident = str(student_identifier).strip()
        records_qs = records_qs.filter(
            Q(student__roll_number__iexact=ident) |
            Q(student__user__username__iexact=ident) |
            Q(student__user__first_name__iexact=ident)
        )

    if subject_code:
        sc = str(subject_code).strip().upper()
        records_qs = records_qs.filter(session__subject__code=sc)

    total_records = records_qs.count()
    # Limit to top 50 most recent records for clean representation
    entries = []
    for r in records_qs[:50]:
        entries.append({
            'record_id': r.id,
            'session_date': str(r.session.session_date),
            'period_number': r.session.period_number,
            'subject_code': r.session.subject.code,
            'subject_title': r.session.subject.title,
            'section': r.session.section.name,
            'student_roll_number': r.student.roll_number,
            'student_name': r.student.user.get_full_name() or r.student.user.username,
            'faculty_name': r.session.faculty.get_full_name() or r.session.faculty.username,
            'status': r.status,
            'remarks': r.remarks or ''
        })

    return {
        'status': 'success',
        'days_window': days,
        'start_date': str(start_date),
        'end_date': str(now),
        'total_matching_records': total_records,
        'records_returned': len(entries),
        'records': entries,
        'message': (
            f"Found {total_records} attendance history records in the last {days} days."
            if total_records > 0
            else f"No attendance history records found in the last {days} days for the specified criteria."
        )
    }


def get_attendance_statistics(time_frame: str = "month", department_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes overall attendance statistics and changes across time (e.g. this month vs previous).
    
    Args:
        time_frame: 'week', 'month', or 'semester'. Defaults to 'month'.
        department_code: Optional department filter (e.g. 'CSE').
        
    Returns:
        Structured dictionary showing trends, conducted sessions, and percentage change.
    """
    today = timezone.localdate()

    if time_frame.lower() == "week":
        days = 7
    elif time_frame.lower() == "semester":
        days = 120
    else:
        # Default month: 30 days
        days = 30

    current_window_start = today - timedelta(days=days)
    previous_window_start = current_window_start - timedelta(days=days)

    base_sessions = AttendanceSession.objects.all()
    if department_code:
        dept_clean = str(department_code).strip().upper()
        base_sessions = base_sessions.filter(section__program__department__code=dept_clean)

    # Current window
    curr_sessions = base_sessions.filter(session_date__gte=current_window_start, session_date__lte=today)
    curr_records = AttendanceRecord.objects.filter(session__in=curr_sessions)
    curr_attended = curr_records.filter(
        status__in=ATTENDED_STATUSES
    ).count()
    curr_total = curr_records.count()
    curr_pct = calculate_attendance_percentage(curr_attended, curr_total)

    # Previous window for comparison
    prev_sessions = base_sessions.filter(session_date__gte=previous_window_start, session_date__lt=current_window_start)
    prev_records = AttendanceRecord.objects.filter(session__in=prev_sessions)
    prev_attended = prev_records.filter(
        status__in=ATTENDED_STATUSES
    ).count()
    prev_total = prev_records.count()
    prev_pct = calculate_attendance_percentage(prev_attended, prev_total)

    # Calculate change
    pct_change = float(curr_pct - prev_pct) if prev_total > 0 else 0.0

    # Daily breakdown in current window
    daily_records = curr_sessions.values('session_date').annotate(
        session_count=Count('id')
    ).order_by('session_date')

    daily_trends = []
    for d in daily_records:
        dt = d['session_date']
        dt_records = curr_records.filter(session__session_date=dt)
        dt_tot = dt_records.count()
        dt_att = dt_records.filter(
            status__in=ATTENDED_STATUSES
        ).count()
        dt_pct = calculate_attendance_percentage(dt_att, dt_tot)
        daily_trends.append({
            'date': str(dt),
            'sessions_conducted': d['session_count'],
            'attendance_percentage': float(dt_pct)
        })

    return {
        'status': 'success',
        'time_frame': time_frame,
        'window_days': days,
        'current_window': {
            'start_date': str(current_window_start),
            'end_date': str(today),
            'sessions_conducted': curr_sessions.count(),
            'total_student_records': curr_total,
            'total_attended': curr_attended,
            'attendance_percentage': float(curr_pct)
        },
        'previous_window': {
            'start_date': str(previous_window_start),
            'end_date': str(current_window_start - timedelta(days=1)),
            'sessions_conducted': prev_sessions.count(),
            'total_student_records': prev_total,
            'total_attended': prev_attended,
            'attendance_percentage': float(prev_pct)
        },
        'percentage_change': pct_change,
        'trend_direction': 'improved' if pct_change > 0 else 'declined' if pct_change < 0 else 'stable',
        'daily_trends': daily_trends,
        'message': (
            f"Over the last {days} days, attendance is at {float(curr_pct)}% across {curr_sessions.count()} sessions "
            f"({'+' if pct_change > 0 else ''}{pct_change}% compared to previous period)."
            if curr_total > 0
            else f"No attendance sessions were conducted in the current {time_frame} timeframe."
        )
    }
