from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import math
from typing import Dict, Any, List, Optional
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied

from .models import (
    AttendanceRecord, AttendanceSession, AttendanceStatus, AttendancePolicy,
    AttendanceCorrection, AttendanceAuditLog, CorrectionStatus, AuditAction
)
from academic.models import Student, Subject, Section, CourseEnrollment, Department, Faculty

User = get_user_model()




def calculate_attendance_percentage(
    attended_classes: int,
    conducted_classes: int,
    rounding_digits: int = 2
) -> Decimal:
    """
    Computes attendance percentage deterministically using exact Decimal arithmetic.
    Formula:
        Attendance % = (Present classes / Conducted classes) * 100

    Precision Rules:
    - Uses Decimal representation for exact base-10 calculation.
    - Rounding: ROUND_HALF_UP (e.g., 66.6666... -> 66.67, 33.3333... -> 33.33).
    - Zero Conducted Classes: returns Decimal('0.00') safely without ZeroDivisionError.
    - Zero Attended Classes: returns Decimal('0.00').
    - 100% Attendance: returns Decimal('100.00').
    - Strictly validated bounds: 0 <= attended_classes <= conducted_classes.

    Raises:
    - ValueError if attended_classes < 0, conducted_classes < 0, or attended > conducted.
    """
    if attended_classes < 0:
        raise ValueError(f"Attended classes cannot be negative: {attended_classes}")
    if conducted_classes < 0:
        raise ValueError(f"Conducted classes cannot be negative: {conducted_classes}")
    if attended_classes > conducted_classes:
        raise ValueError(
            f"Attended classes ({attended_classes}) cannot exceed conducted classes ({conducted_classes})"
        )

    if conducted_classes == 0:
        return Decimal('0.00')

    d_attended = Decimal(str(attended_classes))
    d_conducted = Decimal(str(conducted_classes))

    raw_percentage = (d_attended / d_conducted) * Decimal('100')
    quantize_format = Decimal('0.' + '0' * rounding_digits) if rounding_digits > 0 else Decimal('1')
    return raw_percentage.quantize(quantize_format, rounding=ROUND_HALF_UP)


def is_low_attendance(percentage: Any, threshold: Any = Decimal('75.00')) -> bool:
    """
    Deterministic comparison checking whether an attendance percentage falls strictly below the statutory threshold.
    Formula: percentage < threshold

    Deterministic Edge Cases:
        74.99% < 75.00% -> True  (Low Attendance / At Risk)
        75.00% < 75.00% -> False (Compliant / Eligible)
        75.01% < 75.00% -> False (Compliant / Eligible)
        0.00%  < 75.00% -> True  (Critical Shortage)
        100.00%< 75.00% -> False (Compliant / Eligible)
    """
    if not isinstance(percentage, Decimal):
        percentage = Decimal(str(percentage)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if not isinstance(threshold, Decimal):
        threshold = Decimal(str(threshold)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return percentage < threshold


def get_effective_threshold(custom_threshold: Optional[Any] = None) -> Decimal:
    """
    Returns the effective threshold (Decimal).
    Uses custom_threshold if provided, otherwise retrieves the configured AttendancePolicy threshold.
    Default fallback: Decimal('75.00').
    """
    if custom_threshold is not None:
        try:
            return Decimal(str(custom_threshold)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            pass
    try:
        policy = AttendancePolicy.get_active_policy()
        return policy.default_threshold
    except Exception:
        return Decimal('75.00')


def calculate_classes_needed_for_target(
    attended: int,
    conducted: int,
    target_pct: Decimal = Decimal('75.00')
) -> int:
    """
    Calculates the minimum consecutive classes a student must attend to reach target_pct.
    Formula:
        (attended + x) / (conducted + x) >= target_pct / 100
        x >= (target * conducted - attended) / (1 - target)
    """
    current_pct = calculate_attendance_percentage(attended, conducted)
    if current_pct >= target_pct:
        return 0

    target = target_pct / Decimal('100')
    if target >= Decimal('1'):
        return 0

    numerator = (target * Decimal(conducted)) - Decimal(attended)
    denominator = Decimal('1') - target
    needed = numerator / denominator
    return max(0, math.ceil(float(needed)))


def calculate_classes_can_afford_to_miss(
    attended: int,
    conducted: int,
    target_pct: Decimal = Decimal('75.00')
) -> int:
    """
    Calculates how many future classes a student can afford to miss without dropping below target_pct.
    Formula:
        attended / (conducted + y) >= target_pct / 100
        y <= (attended / target) - conducted
    """
    current_pct = calculate_attendance_percentage(attended, conducted)
    if current_pct < target_pct:
        return 0

    target = target_pct / Decimal('100')
    if target <= Decimal('0'):
        return 0

    max_conducted = Decimal(attended) / target
    margin = max_conducted - Decimal(conducted)
    return max(0, math.floor(float(margin)))


class AttendanceStatusCategory:
    ELIGIBLE = 'ELIGIBLE'                # >= 75%
    CONDONATION_REQUIRED = 'CONDONATION' # 65% - 74.99%
    CRITICAL_SHORTAGE = 'CRITICAL'       # < 65%
    NO_DATA = 'NO_DATA'                  # 0 classes conducted


def get_attendance_status_category(
    percentage: Decimal,
    conducted: int,
    min_pct: float = 75.0,
    condonation_min_pct: float = 65.0
) -> str:
    """Categorizes attendance percentage into statutory compliance bands."""
    if conducted == 0:
        return AttendanceStatusCategory.NO_DATA
    d_min = Decimal(str(min_pct))
    d_cond = Decimal(str(condonation_min_pct))
    if percentage >= d_min:
        return AttendanceStatusCategory.ELIGIBLE
    elif percentage >= d_cond:
        return AttendanceStatusCategory.CONDONATION_REQUIRED
    else:
        return AttendanceStatusCategory.CRITICAL_SHORTAGE


class AttendanceCalculationService:
    """
    Statutory Attendance Calculation & Low-Attendance Detection Engine.
    Provides deterministic calculation of:
    - Classes conducted, attended, missed
    - Attendance percentage (Decimal)
    - Subject-wise and overall attendance
    - Low attendance detection against configurable threshold (default 75%)
    - Warning notifications and recovery roadmaps
    - Administrative and faculty compliance reports
    """

    @classmethod
    def calculate_student_subject_attendance(
        cls,
        student: Student,
        subject: Subject,
        include_authorized_leaves: bool = True,
        threshold: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Calculates attendance statistics for a single student in a specific subject,
        evaluating low-attendance status against the threshold.
        """
        effective_thresh = get_effective_threshold(threshold)

        records = AttendanceRecord.objects.filter(
            student=student,
            session__subject=subject
        )

        conducted_classes = records.count()
        present_count = records.filter(status=AttendanceStatus.PRESENT).count()
        late_count = records.filter(status=AttendanceStatus.LATE).count()
        on_duty_count = records.filter(status=AttendanceStatus.ON_DUTY).count()
        medical_count = records.filter(status=AttendanceStatus.MEDICAL_LEAVE).count()
        absent_count = records.filter(status=AttendanceStatus.ABSENT).count()

        if include_authorized_leaves:
            attended_classes = present_count + late_count + on_duty_count + medical_count
        else:
            attended_classes = present_count + late_count

        missed_classes = conducted_classes - attended_classes
        attendance_pct = calculate_attendance_percentage(attended_classes, conducted_classes)
        pure_present_pct = calculate_attendance_percentage(present_count, conducted_classes)

        min_pct = getattr(subject, 'min_attendance_pct', float(effective_thresh))
        cond_min_pct = getattr(subject, 'condonation_min_pct', 65.0)

        # Low attendance boolean check (deterministic: percentage < threshold)
        low_attendance_flag = is_low_attendance(attendance_pct, effective_thresh) if conducted_classes > 0 else False
        deficit_pct = max(Decimal('0.00'), effective_thresh - attendance_pct) if low_attendance_flag else Decimal('0.00')

        status_cat = get_attendance_status_category(
            attendance_pct, conducted_classes, min_pct, cond_min_pct
        )
        classes_needed = calculate_classes_needed_for_target(
            attended_classes, conducted_classes, effective_thresh
        )
        classes_can_miss = calculate_classes_can_afford_to_miss(
            attended_classes, conducted_classes, effective_thresh
        )

        return {
            'subject_id': subject.id,
            'subject_code': subject.code,
            'subject_title': subject.title,
            'credits': subject.credits,
            'classes_conducted': conducted_classes,
            'classes_attended': attended_classes,
            'classes_missed': missed_classes,
            'attendance_percentage': float(attendance_pct),
            'attendance_percentage_decimal': str(attendance_pct),
            'pure_present_percentage': float(pure_present_pct),
            'present_count': present_count,
            'late_count': late_count,
            'on_duty_count': on_duty_count,
            'medical_count': medical_count,
            'absent_count': absent_count,
            'threshold_used': float(effective_thresh),
            'is_low_attendance': low_attendance_flag,
            'deficit_percentage': float(deficit_pct),
            'statutory_min_pct': min_pct,
            'condonation_min_pct': cond_min_pct,
            'status': status_cat,
            'is_eligible': status_cat == AttendanceStatusCategory.ELIGIBLE,
            'needs_condonation': status_cat == AttendanceStatusCategory.CONDONATION_REQUIRED,
            'is_critical': status_cat == AttendanceStatusCategory.CRITICAL_SHORTAGE,
            'classes_needed_for_75': classes_needed,
            'classes_can_miss_for_75': classes_can_miss,
        }

    @classmethod
    def calculate_student_overall_attendance(
        cls,
        student: Student,
        include_authorized_leaves: bool = True,
        threshold: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Calculates aggregate overall attendance across all enrolled subjects for a student,
        evaluating overall and subject-level low-attendance status.
        """
        effective_thresh = get_effective_threshold(threshold)

        enrollments = CourseEnrollment.objects.filter(
            student=student,
            is_active=True
        ).select_related('subject')

        enrolled_subjects = [e.subject for e in enrollments]
        if not enrolled_subjects:
            enrolled_subjects = list(
                Subject.objects.filter(
                    department=student.section.program.department,
                    semester=student.section.semester
                )
            )

        subject_summaries = []
        total_conducted = 0
        total_attended = 0
        total_missed = 0
        total_present = 0
        total_late = 0
        total_on_duty = 0
        total_medical = 0
        total_absent = 0

        eligible_count = 0
        condonation_count = 0
        critical_count = 0
        low_attendance_subjects_count = 0

        for subject in enrolled_subjects:
            summary = cls.calculate_student_subject_attendance(
                student, subject, include_authorized_leaves=include_authorized_leaves, threshold=effective_thresh
            )
            subject_summaries.append(summary)

            total_conducted += summary['classes_conducted']
            total_attended += summary['classes_attended']
            total_missed += summary['classes_missed']
            total_present += summary['present_count']
            total_late += summary['late_count']
            total_on_duty += summary['on_duty_count']
            total_medical += summary['medical_count']
            total_absent += summary['absent_count']

            if summary['is_low_attendance']:
                low_attendance_subjects_count += 1

            if summary['status'] == AttendanceStatusCategory.ELIGIBLE:
                eligible_count += 1
            elif summary['status'] == AttendanceStatusCategory.CONDONATION_REQUIRED:
                condonation_count += 1
            elif summary['status'] == AttendanceStatusCategory.CRITICAL_SHORTAGE:
                critical_count += 1

        overall_pct = calculate_attendance_percentage(total_attended, total_conducted)
        overall_low_attendance = is_low_attendance(overall_pct, effective_thresh) if total_conducted > 0 else False
        overall_status = get_attendance_status_category(overall_pct, total_conducted, min_pct=float(effective_thresh))

        classes_needed_overall = calculate_classes_needed_for_target(total_attended, total_conducted, effective_thresh)
        classes_can_miss_overall = calculate_classes_can_afford_to_miss(total_attended, total_conducted, effective_thresh)

        return {
            'student_id': student.id,
            'roll_number': student.roll_number,
            'full_name': student.user.get_full_name(),
            'section_id': student.section.id,
            'section_label': str(student.section),
            'department_name': student.section.program.department.name,
            'threshold_used': float(effective_thresh),
            'total_conducted': total_conducted,
            'total_attended': total_attended,
            'total_missed': total_missed,
            'overall_percentage': float(overall_pct),
            'overall_percentage_decimal': str(overall_pct),
            'is_low_attendance': overall_low_attendance,
            'overall_status': overall_status,
            'is_overall_eligible': not overall_low_attendance,
            'classes_needed_for_target': classes_needed_overall,
            'classes_can_miss_for_target': classes_can_miss_overall,
            'counts': {
                'present': total_present,
                'late': total_late,
                'on_duty': total_on_duty,
                'medical': total_medical,
                'absent': total_absent,
            },
            'subject_stats': {
                'total_enrolled_subjects': len(subject_summaries),
                'eligible_subjects_count': eligible_count,
                'condonation_subjects_count': condonation_count,
                'critical_shortage_subjects_count': critical_count,
                'low_attendance_subjects_count': low_attendance_subjects_count,
            },
            'subjects': subject_summaries,
        }

    @classmethod
    def generate_student_warnings(
        cls,
        student: Student,
        threshold: Optional[Decimal] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates individual attendance warning notices for a student in subjects
        where attendance falls below the threshold.
        """
        overall_summary = cls.calculate_student_overall_attendance(student, threshold=threshold)
        effective_thresh = Decimal(str(overall_summary['threshold_used']))

        warnings = []
        for sub in overall_summary['subjects']:
            if sub['is_low_attendance'] and sub['classes_conducted'] > 0:
                pct = Decimal(str(sub['attendance_percentage']))
                cond_floor = Decimal(str(sub['condonation_min_pct']))
                is_debarment = pct < cond_floor

                severity = 'CRITICAL_DEBARMENT' if is_debarment else 'STATUTORY_WARNING'
                needed = sub['classes_needed_for_75']

                message = (
                    f"Statutory Warning: Your attendance in {sub['subject_code']} ({sub['attendance_percentage']}%) "
                    f"is below the required {effective_thresh}% threshold. You must attend the next {needed} consecutive class(es) "
                    f"to prevent semester examination debarment."
                )

                warnings.append({
                    'subject_id': sub['subject_id'],
                    'subject_code': sub['subject_code'],
                    'subject_title': sub['subject_title'],
                    'current_percentage': sub['attendance_percentage'],
                    'threshold': float(effective_thresh),
                    'deficit_percentage': round(float(effective_thresh - pct), 2),
                    'severity': severity,
                    'classes_conducted': sub['classes_conducted'],
                    'classes_attended': sub['classes_attended'],
                    'classes_missed': sub['classes_missed'],
                    'classes_needed_to_recover': needed,
                    'is_debarment_risk': is_debarment,
                    'warning_message': message,
                    'generated_at': timezone.now().isoformat(),
                })

        return warnings

    @classmethod
    def get_low_attendance_students_list(
        cls,
        filters: Optional[Dict[str, Any]] = None,
        threshold: Optional[Decimal] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns a list of students with low attendance (overall or in a subject),
        with optional filtering by department, section, or subject.
        """
        effective_thresh = get_effective_threshold(threshold)
        filters = filters or {}

        students_qs = Student.objects.filter(user__is_active=True).select_related(
            'user', 'section__program__department'
        )


        if 'department_id' in filters and filters['department_id']:
            students_qs = students_qs.filter(section__program__department_id=filters['department_id'])
        if 'section_id' in filters and filters['section_id']:
            students_qs = students_qs.filter(section_id=filters['section_id'])

        subject_id = filters.get('subject_id')
        subject = None
        if subject_id:
            subject = Subject.objects.filter(id=subject_id).first()

        low_attendance_list = []
        for student in students_qs:
            if subject:
                sub_stat = cls.calculate_student_subject_attendance(student, subject, threshold=effective_thresh)
                if sub_stat['is_low_attendance'] and sub_stat['classes_conducted'] > 0:
                    low_attendance_list.append({
                        'student_id': student.id,
                        'roll_number': student.roll_number,
                        'full_name': student.user.get_full_name(),
                        'email': student.user.email,
                        'section_id': student.section.id,
                        'section_label': str(student.section),
                        'department_name': student.section.program.department.name,
                        'subject_code': subject.code,
                        'subject_title': subject.title,
                        'attendance_percentage': sub_stat['attendance_percentage'],
                        'threshold_used': float(effective_thresh),
                        'classes_conducted': sub_stat['classes_conducted'],
                        'classes_attended': sub_stat['classes_attended'],
                        'classes_missed': sub_stat['classes_missed'],
                        'classes_needed_to_recover': sub_stat['classes_needed_for_75'],
                        'severity': sub_stat['status'],
                    })
            else:
                overall_stat = cls.calculate_student_overall_attendance(student, threshold=effective_thresh)
                if overall_stat['is_low_attendance'] and overall_stat['total_conducted'] > 0:
                    low_attendance_list.append({
                        'student_id': student.id,
                        'roll_number': student.roll_number,
                        'full_name': student.user.get_full_name(),
                        'email': student.user.email,
                        'section_id': student.section.id,
                        'section_label': str(student.section),
                        'department_name': student.section.program.department.name,
                        'overall_percentage': overall_stat['overall_percentage'],
                        'threshold_used': float(effective_thresh),
                        'total_conducted': overall_stat['total_conducted'],
                        'total_attended': overall_stat['total_attended'],
                        'total_missed': overall_stat['total_missed'],
                        'classes_needed_to_recover': overall_stat['classes_needed_for_target'],
                        'severity': overall_stat['overall_status'],
                        'low_subjects_count': overall_stat['subject_stats']['low_attendance_subjects_count'],
                    })

        return low_attendance_list

    @classmethod
    def generate_admin_report(cls, threshold: Optional[Decimal] = None) -> Dict[str, Any]:
        """
        Generates comprehensive institution-wide low-attendance audit report for Dean & Academic Admin.
        """
        effective_thresh = get_effective_threshold(threshold)
        all_students = Student.objects.filter(user__is_active=True).select_related('section__program__department', 'user')

        total_evaluated = all_students.count()
        low_attendance_students = []
        dept_stats: Dict[str, Dict[str, Any]] = {}

        for student in all_students:
            dept_name = student.section.program.department.name
            if dept_name not in dept_stats:
                dept_stats[dept_name] = {
                    'department_name': dept_name,
                    'total_students': 0,
                    'low_attendance_count': 0,
                    'critical_count': 0,
                }
            dept_stats[dept_name]['total_students'] += 1

            summary = cls.calculate_student_overall_attendance(student, threshold=effective_thresh)
            if summary['is_low_attendance'] and summary['total_conducted'] > 0:
                low_attendance_students.append(summary)
                dept_stats[dept_name]['low_attendance_count'] += 1
                if summary['overall_status'] == AttendanceStatusCategory.CRITICAL_SHORTAGE:
                    dept_stats[dept_name]['critical_count'] += 1

        # Calculate departmental percentages
        for d in dept_stats.values():
            if d['total_students'] > 0:
                d_pct = round((d['low_attendance_count'] / d['total_students']) * 100, 2)
            else:
                d_pct = 0.0
            d['low_attendance_percentage'] = d_pct

        at_risk_pct = round((len(low_attendance_students) / total_evaluated * 100), 2) if total_evaluated > 0 else 0.0

        return {
            'report_name': 'Institutional Statutory Attendance Audit Report',
            'generated_at': timezone.now().isoformat(),
            'threshold_used': float(effective_thresh),
            'total_students_evaluated': total_evaluated,
            'total_low_attendance_students': len(low_attendance_students),
            'institutional_at_risk_percentage': at_risk_pct,
            'departments': list(dept_stats.values()),
            'top_critical_students': [
                {
                    'roll_number': s['roll_number'],
                    'full_name': s['full_name'],
                    'section': s['section_label'],
                    'department': s['department_name'],
                    'overall_percentage': s['overall_percentage'],
                    'conducted': s['total_conducted'],
                    'attended': s['total_attended'],
                    'status': s['overall_status'],
                    'classes_needed': s['classes_needed_for_target'],
                }
                for s in sorted(low_attendance_students, key=lambda x: x['overall_percentage'])[:15]
            ],
        }

    @classmethod
    def generate_faculty_report(cls, faculty_user: User, threshold: Optional[Decimal] = None) -> Dict[str, Any]:
        """
        Generates scoped low-attendance report for all sections and courses assigned to a faculty member.
        """
        effective_thresh = get_effective_threshold(threshold)

        # Get all sections taught or mentored by faculty
        allocations = CourseEnrollment.objects.none()
        try:
            faculty = faculty_user.faculty_profile
            faculty_allocations = faculty.allocations.filter(is_active=True).select_related('section', 'subject')
        except Faculty.DoesNotExist:
            faculty_allocations = []

        mentored_sections = Section.objects.filter(mentor=faculty_user)

        # Collect unique sections
        monitored_sections = set([a.section for a in faculty_allocations] + list(mentored_sections))

        section_reports = []
        all_monitored_students = set()
        at_risk_students_list = []

        for section in monitored_sections:
            students = Student.objects.filter(section=section, user__is_active=True).select_related('user')
            all_monitored_students.update(students)

            sec_low_count = 0
            for student in students:
                summary = cls.calculate_student_overall_attendance(student, threshold=effective_thresh)
                if summary['is_low_attendance'] and summary['total_conducted'] > 0:
                    sec_low_count += 1
                    at_risk_students_list.append({
                        'student_id': student.id,
                        'roll_number': student.roll_number,
                        'full_name': student.user.get_full_name(),
                        'section_label': str(section),
                        'overall_percentage': summary['overall_percentage'],
                        'status': summary['overall_status'],
                        'classes_needed_for_75': summary['classes_needed_for_target'],
                        'classes_conducted': summary['total_conducted'],
                        'classes_attended': summary['total_attended'],
                    })

            section_reports.append({
                'section_id': section.id,
                'section_label': str(section),
                'total_students': students.count(),
                'low_attendance_count': sec_low_count,
            })

        total_monitored = len(all_monitored_students)
        total_at_risk = len(at_risk_students_list)
        at_risk_pct = round((total_at_risk / total_monitored * 100), 2) if total_monitored > 0 else 0.0

        return {
            'faculty_name': faculty_user.get_full_name(),
            'generated_at': timezone.now().isoformat(),
            'threshold_used': float(effective_thresh),
            'total_students_monitored': total_monitored,
            'total_at_risk_students': total_at_risk,
            'at_risk_percentage': at_risk_pct,
            'sections': section_reports,
            'at_risk_students': sorted(at_risk_students_list, key=lambda x: x['overall_percentage']),
        }

    @classmethod
    def calculate_section_attendance_summary(
        cls,
        section: Section,
        subject: Optional[Subject] = None,
        threshold: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Calculates section/class cohort level attendance metrics for faculty, HOD, and mentor reviews.
        """
        effective_thresh = get_effective_threshold(threshold)
        students = Student.objects.filter(section=section, user__is_active=True).select_related('user')
        student_summaries = []

        total_class_conducted = 0
        total_class_attended = 0

        above_75 = 0
        between_65_75 = 0
        below_65 = 0

        for student in students:
            if subject:
                s_sum = cls.calculate_student_subject_attendance(student, subject, threshold=effective_thresh)
                student_pct = Decimal(str(s_sum['attendance_percentage']))
                conducted = s_sum['classes_conducted']
                attended = s_sum['classes_attended']
            else:
                s_sum = cls.calculate_student_overall_attendance(student, threshold=effective_thresh)
                student_pct = Decimal(str(s_sum['overall_percentage']))
                conducted = s_sum['total_conducted']
                attended = s_sum['total_attended']

            student_summaries.append({
                'student_id': student.id,
                'roll_number': student.roll_number,
                'full_name': student.user.get_full_name(),
                'attendance_percentage': float(student_pct),
                'status': s_sum.get('status') or s_sum.get('overall_status'),
                'is_low_attendance': s_sum.get('is_low_attendance', False),
                'classes_conducted': conducted,
                'classes_attended': attended,
            })

            total_class_conducted += conducted
            total_class_attended += attended

            if conducted > 0:
                if student_pct >= effective_thresh:
                    above_75 += 1
                elif student_pct >= Decimal('65.00'):
                    between_65_75 += 1
                else:
                    below_65 += 1

        class_avg_pct = calculate_attendance_percentage(total_class_attended, total_class_conducted)

        return {
            'section_id': section.id,
            'section_label': str(section),
            'subject_code': subject.code if subject else 'ALL_SUBJECTS',
            'subject_title': subject.title if subject else 'All Enrolled Subjects Aggregate',
            'total_students': students.count(),
            'threshold_used': float(effective_thresh),
            'class_average_percentage': float(class_avg_pct),
            'class_average_percentage_decimal': str(class_avg_pct),
            'distribution': {
                'eligible_above_75': above_75,
                'condonation_65_to_75': between_65_75,
                'critical_below_65': below_65,
            },
            'students': sorted(student_summaries, key=lambda x: x['roll_number']),
        }

    @classmethod
    def get_admin_dashboard_summary(cls, threshold: Optional[Decimal] = None) -> Dict[str, Any]:
        """
        Calculates all institutional metrics for the Admin Dashboard:
        - Total students
        - Total faculty
        - Departments
        - Overall attendance
        - Low attendance students
        - Attendance by department
        - Attendance trends
        """
        effective_thresh = get_effective_threshold(threshold)
        total_students = Student.objects.filter(user__is_active=True).count()
        total_faculty = Faculty.objects.filter(user__is_active=True).count()
        departments_qs = Department.objects.prefetch_related('programs').all()

        admin_rep = cls.generate_admin_report(threshold=effective_thresh)
        dept_stats = admin_rep['departments']
        low_attendance_students = admin_rep['top_critical_students']
        total_low_attendance = admin_rep['total_low_attendance_students']

        total_sessions_count = AttendanceSession.objects.count()
        total_records = AttendanceRecord.objects.count()
        total_present = AttendanceRecord.objects.filter(
            status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.ON_DUTY, AttendanceStatus.MEDICAL_LEAVE]
        ).count()
        overall_inst_pct = calculate_attendance_percentage(total_present, total_records)

        # Recent 7 session dates trend
        recent_dates = list(
            AttendanceSession.objects.values_list('session_date', flat=True)
            .distinct()
            .order_by('-session_date')[:7]
        )
        recent_dates.reverse()

        trends = []
        for d in recent_dates:
            d_records = AttendanceRecord.objects.filter(session__session_date=d)
            d_total = d_records.count()
            d_pres = d_records.filter(
                status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.ON_DUTY, AttendanceStatus.MEDICAL_LEAVE]
            ).count()
            d_pct = calculate_attendance_percentage(d_pres, d_total)
            d_sessions = AttendanceSession.objects.filter(session_date=d).count()
            trends.append({
                'date': d.isoformat(),
                'total_sessions': d_sessions,
                'total_records': d_total,
                'attended_records': d_pres,
                'attendance_percentage': float(d_pct),
            })

        return {
            'total_students': total_students,
            'total_faculty': total_faculty,
            'total_departments': departments_qs.count(),
            'total_sessions': total_sessions_count,
            'overall_attendance_percentage': float(overall_inst_pct),
            'overall_attendance_percentage_decimal': str(overall_inst_pct),
            'threshold_used': float(effective_thresh),
            'low_attendance_count': total_low_attendance,
            'institutional_at_risk_percentage': admin_rep['institutional_at_risk_percentage'],
            'departments': dept_stats,
            'low_attendance_students': low_attendance_students,
            'attendance_trends': trends,
        }

    @classmethod
    def get_faculty_dashboard_summary(cls, faculty_user: User, threshold: Optional[Decimal] = None) -> Dict[str, Any]:
        """
        Calculates all classroom and cohort metrics for the Faculty Dashboard:
        - Today's classes
        - Pending attendance
        - Class attendance
        - Low attendance students
        """
        effective_thresh = get_effective_threshold(threshold)
        today = timezone.localdate()

        allocations = []
        try:
            if hasattr(faculty_user, 'faculty_profile'):
                allocations = list(
                    faculty_user.faculty_profile.allocations.filter(is_active=True)
                    .select_related('section__program__department', 'subject')
                )
        except Exception:
            allocations = []

        today_classes = []
        pending_count = 0

        for alloc in allocations:
            session_today = AttendanceSession.objects.filter(
                faculty=faculty_user,
                section=alloc.section,
                subject=alloc.subject,
                session_date=today
            ).first()

            is_recorded = session_today is not None
            if not is_recorded:
                pending_count += 1

            student_count = Student.objects.filter(section=alloc.section, user__is_active=True).count()

            today_classes.append({
                'allocation_id': alloc.id,
                'section_id': alloc.section.id,
                'section_name': alloc.section.name,
                'section_label': str(alloc.section),
                'department_code': alloc.section.program.department.code,
                'subject_id': alloc.subject.id,
                'subject_code': alloc.subject.code,
                'subject_title': alloc.subject.title,
                'total_students': student_count,
                'is_attendance_taken': is_recorded,
                'session_id': session_today.id if session_today else None,
                'attendance_percentage': session_today.attendance_percentage if session_today else None,
                'period_number': session_today.period_number if session_today else 1,
            })

        class_attendance = []
        for alloc in allocations:
            summary = cls.calculate_section_attendance_summary(
                alloc.section, subject=alloc.subject, threshold=effective_thresh
            )
            class_attendance.append({
                'section_id': alloc.section.id,
                'section_label': str(alloc.section),
                'subject_code': alloc.subject.code,
                'subject_title': alloc.subject.title,
                'total_students': summary['total_students'],
                'class_average_percentage': summary['class_average_percentage'],
                'distribution': summary['distribution'],
            })

        faculty_rep = cls.generate_faculty_report(faculty_user, threshold=effective_thresh)
        at_risk_students = faculty_rep.get('at_risk_students', [])

        return {
            'faculty_name': faculty_user.get_full_name(),
            'today': today.isoformat(),
            'threshold_used': float(effective_thresh),
            'total_allocations': len(allocations),
            'today_classes_count': len(today_classes),
            'pending_attendance_count': pending_count,
            'today_classes': today_classes,
            'class_attendance': class_attendance,
            'low_attendance_students': at_risk_students,
        }

    @classmethod
    def get_student_dashboard_summary(cls, student_user: User, threshold: Optional[Decimal] = None) -> Dict[str, Any]:
        """
        Calculates student-specific metrics for the Student Dashboard:
        - Overall attendance
        - Subject-wise attendance
        - Attendance history
        - Low attendance warnings
        """
        effective_thresh = get_effective_threshold(threshold)
        student = student_user.student_profile

        overall_stat = cls.calculate_student_overall_attendance(student, threshold=effective_thresh)
        warnings = cls.generate_student_warnings(student, threshold=effective_thresh)

        records = AttendanceRecord.objects.filter(student=student).select_related(
            'session__subject', 'session__faculty'
        ).order_by('-session__session_date', '-session__period_number')[:20]

        history = [
            {
                'record_id': r.id,
                'session_id': r.session.id,
                'session_date': r.session.session_date.isoformat(),
                'period_number': r.session.period_number,
                'subject_code': r.session.subject.code,
                'subject_title': r.session.subject.title,
                'faculty_name': r.session.faculty.get_full_name(),
                'status': r.status,
                'status_display': r.get_status_display(),
                'remarks': r.remarks,
                'marked_at': r.marked_at.isoformat(),
            }
            for r in records
        ]

        return {
            'student': {
                'id': student.id,
                'roll_number': student.roll_number,
                'registration_number': student.registration_number,
                'full_name': student_user.get_full_name(),
                'email': student_user.email,
                'department_name': student.section.program.department.name,
                'program_name': student.section.program.name,
                'section_label': str(student.section),
                'semester': student.section.semester,
                'mentor_name': student.section.mentor.get_full_name() if student.section.mentor else 'Unassigned',
            },
            'threshold_used': float(effective_thresh),
            'overall_attendance': {
                'total_conducted': overall_stat['total_conducted'],
                'total_attended': overall_stat['total_attended'],
                'total_missed': overall_stat['total_missed'],
                'overall_percentage': overall_stat['overall_percentage'],
                'overall_status': overall_stat['overall_status'],
                'is_low_attendance': overall_stat['is_low_attendance'],
                'classes_needed_for_target': overall_stat['classes_needed_for_target'],
                'classes_can_miss_for_target': overall_stat['classes_can_miss_for_target'],
                'counts': overall_stat['counts'],
            },
            'subject_wise_attendance': overall_stat['subjects'],
            'attendance_history': history,
            'low_attendance_warnings': {
                'has_warnings': len(warnings) > 0,
                'warnings_count': len(warnings),
                'warnings': warnings,
            },
        }



class AttendanceCorrectionService:
    """
    Deterministic Attendance Correction & Dispute Resolution Workflow Engine.
    Handles:
    1. Submission of formal correction requests by students or faculty.
    2. Automatic capture of original attendance status and timestamp.
    3. Multi-tier role-based authorization verification (Strictly prevents students from approving).
    4. Deterministic approval workflow:
       - Never silently overwrites attendance.
       - Updates record status within an atomic transaction.
       - Emits immutable AttendanceAuditLog entry capturing old/new status, actor, reason, timestamp.
    5. Deterministic rejection workflow:
       - Retains original attendance status unaltered.
       - Emits immutable AttendanceAuditLog entry documenting rejection rationale.
    6. Role-scoped audit history queries.
    """

    @classmethod
    def request_correction(
        cls,
        record_id: int,
        requested_by: User,
        requested_status: str,
        reason: str,
        document_url: str = ""
    ) -> AttendanceCorrection:
        """
        Submits an attendance correction request.
        Auto-populates:
        - old_status: exactly current record.status
        - requester: requested_by
        - status: PENDING
        - timestamp: auto_now_add
        """
        try:
            record = AttendanceRecord.objects.select_related('student__user', 'session__subject').get(id=record_id)
        except AttendanceRecord.DoesNotExist:
            raise ValidationError(f"Attendance record with ID {record_id} does not exist.")

        # If requester is a student, verify they own the record
        if requested_by.is_student_role:
            if record.student.user != requested_by:
                raise PermissionDenied("Students can only submit correction requests for their own attendance records.")

        if requested_status not in AttendanceStatus.values:
            raise ValidationError(f"Invalid requested status '{requested_status}'. Must be one of {AttendanceStatus.values}.")

        # Cannot request the status that is already marked
        if requested_status == record.status:
            raise ValidationError(
                f"Requested status '{requested_status}' is identical to the current attendance status."
            )

        # Check for active pending request on this record
        if AttendanceCorrection.objects.filter(record=record, status=CorrectionStatus.PENDING).exists():
            raise ValidationError("A pending correction request already exists for this attendance record.")

        reason = (reason or "").strip()
        if not reason or len(reason) < 5:
            raise ValidationError("A detailed justification (minimum 5 characters) is required for attendance correction.")

        correction = AttendanceCorrection.objects.create(
            record=record,
            requested_by=requested_by,
            old_status=record.status,
            requested_status=requested_status,
            reason=reason,
            document_url=(document_url or "").strip(),
            status=CorrectionStatus.PENDING
        )
        return correction

    @classmethod
    def is_authorized_to_review(cls, correction: AttendanceCorrection, user: User) -> bool:
        """
        Determines whether the given user is authorized to approve or reject a correction request.
        Rules:
        - Students are NEVER authorized to approve or reject.
        - Institutional Admins and HODs are authorized.
        - Faculty who conducted the attendance session is authorized.
        - Faculty allocated to the subject/section is authorized.
        - Faculty assigned as Section Mentor is authorized.
        """
        if user.is_student_role or not user.is_authenticated:
            return False

        if user.is_admin_role or user.is_hod_role:
            return True

        session = correction.record.session
        # Session faculty
        if session.faculty == user:
            return True

        # Section mentor
        if session.section.mentor == user:
            return True

        # Allocated faculty
        try:
            if hasattr(user, 'faculty_profile'):
                if user.faculty_profile.allocations.filter(
                    section=session.section,
                    subject=session.subject,
                    is_active=True
                ).exists():
                    return True
        except Exception:
            pass

        return False

    @classmethod
    def approve_correction(
        cls,
        correction_id: int,
        reviewed_by: User,
        review_notes: str = "",
        ip_address: Optional[str] = None
    ) -> AttendanceCorrection:
        """
        Approves an attendance correction request.
        Guarantees:
        - Only authorized staff can approve (Students strictly blocked).
        - Historical record is NOT silently overwritten.
        - Atomically reconciles AttendanceRecord.status and writes append-only AttendanceAuditLog.
        """
        try:
            correction = AttendanceCorrection.objects.select_related(
                'record__session__faculty',
                'record__session__section__mentor',
                'record__student__user',
                'record__session__subject'
            ).get(id=correction_id)
        except AttendanceCorrection.DoesNotExist:
            raise ValidationError(f"Correction request #{correction_id} does not exist.")

        if correction.status != CorrectionStatus.PENDING:
            raise ValidationError(
                f"Correction request #{correction_id} is already {correction.get_status_display()} and cannot be modified."
            )

        if not cls.is_authorized_to_review(correction, reviewed_by):
            raise PermissionDenied("You are not authorized to approve this attendance correction.")

        with transaction.atomic():
            record = correction.record
            original_status = record.status

            # Update the attendance record with the approved status
            record.status = correction.requested_status
            record.save(update_fields=['status', 'marked_at'])

            # Create immutable audit log entry
            audit_reason = review_notes.strip() if review_notes else f"Approved correction: {correction.reason}"
            AttendanceAuditLog.objects.create(
                record=record,
                action=AuditAction.CORRECTION_APPROVED,
                previous_status=original_status,
                new_status=correction.requested_status,
                changed_by=reviewed_by,
                reason=audit_reason,
                ip_address=ip_address
            )

            # Update correction status
            correction.status = CorrectionStatus.APPROVED
            correction.reviewed_by = reviewed_by
            correction.review_notes = (review_notes or "").strip()
            correction.resolved_at = timezone.now()
            correction.save(update_fields=['status', 'reviewed_by', 'review_notes', 'resolved_at'])

        return correction

    @classmethod
    def reject_correction(
        cls,
        correction_id: int,
        reviewed_by: User,
        review_notes: str = "",
        ip_address: Optional[str] = None
    ) -> AttendanceCorrection:
        """
        Rejects an attendance correction request.
        Guarantees:
        - Original attendance status remains completely unchanged.
        - Emits an append-only audit trail logging the rejection decision and rationale.
        """
        try:
            correction = AttendanceCorrection.objects.select_related(
                'record__session__faculty',
                'record__session__section__mentor',
                'record__student__user',
                'record__session__subject'
            ).get(id=correction_id)
        except AttendanceCorrection.DoesNotExist:
            raise ValidationError(f"Correction request #{correction_id} does not exist.")

        if correction.status != CorrectionStatus.PENDING:
            raise ValidationError(
                f"Correction request #{correction_id} is already {correction.get_status_display()} and cannot be modified."
            )

        if not cls.is_authorized_to_review(correction, reviewed_by):
            raise PermissionDenied("You are not authorized to reject this attendance correction.")

        with transaction.atomic():
            record = correction.record

            # AttendanceRecord status is NOT modified!
            # Emitting rejection audit entry
            audit_reason = review_notes.strip() if review_notes else "Correction request rejected after review"
            AttendanceAuditLog.objects.create(
                record=record,
                action=AuditAction.CORRECTION_REJECTED,
                previous_status=record.status,
                new_status=record.status,
                changed_by=reviewed_by,
                reason=audit_reason,
                ip_address=ip_address
            )

            # Update correction status
            correction.status = CorrectionStatus.REJECTED
            correction.reviewed_by = reviewed_by
            correction.review_notes = (review_notes or "").strip()
            correction.resolved_at = timezone.now()
            correction.save(update_fields=['status', 'reviewed_by', 'review_notes', 'resolved_at'])

        return correction

    @classmethod
    def get_scoped_corrections(cls, user: User, filters: Optional[Dict[str, Any]] = None):
        """
        Returns correction requests scoped strictly to the requesting user's role.
        """
        filters = filters or {}
        qs = AttendanceCorrection.objects.select_related(
            'record__student__user',
            'record__session__subject',
            'record__session__section',
            'requested_by',
            'reviewed_by'
        ).all()

        if user.is_student_role:
            qs = qs.filter(Q(record__student__user=user) | Q(requested_by=user))
        elif not (user.is_admin_role or user.is_hod_role):
            # Faculty
            qs = qs.filter(
                Q(record__session__faculty=user) |
                Q(record__session__section__mentor=user) |
                Q(record__session__section__allocations__faculty__user=user)
            ).distinct()

        # Query filters
        status_filter = filters.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        record_id = filters.get('record_id')
        if record_id:
            qs = qs.filter(record_id=record_id)

        student_id = filters.get('student_id')
        if student_id:
            qs = qs.filter(record__student_id=student_id)

        return qs.order_by('-created_at')

    @classmethod
    def get_scoped_audit_logs(cls, user: User, filters: Optional[Dict[str, Any]] = None):
        """
        Returns audit logs scoped strictly to the requesting user's role.
        """
        filters = filters or {}
        qs = AttendanceAuditLog.objects.select_related(
            'record__student__user',
            'record__session__subject',
            'changed_by'
        ).all()

        if user.is_student_role:
            qs = qs.filter(record__student__user=user)
        elif not (user.is_admin_role or user.is_hod_role):
            # Faculty
            qs = qs.filter(
                Q(record__session__faculty=user) |
                Q(record__session__section__mentor=user) |
                Q(record__session__section__allocations__faculty__user=user)
            ).distinct()

        record_id = filters.get('record_id')
        if record_id:
            qs = qs.filter(record_id=record_id)

        student_id = filters.get('student_id')
        if student_id:
            qs = qs.filter(record__student_id=student_id)

        action_filter = filters.get('action')
        if action_filter:
            qs = qs.filter(action=action_filter)

        return qs.order_by('-timestamp')

