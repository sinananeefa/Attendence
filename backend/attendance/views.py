from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from accounts.permissions import (
    IsAdminUserRole, IsFacultyUserRole, IsStudentUserRole
)
from academic.models import Section, Subject, Student, Faculty, FacultyAllocation, CourseEnrollment
from .models import (
    AttendanceSession, AttendanceRecord, AttendanceCorrection, AttendanceAuditLog,
    AttendanceStatus, SessionStatus, SessionType, AuditAction, AttendancePolicy
)
from .serializers import (
    AttendanceSessionSerializer, AttendanceSessionDetailSerializer,
    AttendanceRecordSerializer, BatchAttendanceRecordSerializer,
    AttendanceCorrectionSerializer, AttendanceAuditLogSerializer,
    CreateAttendanceCorrectionSerializer, ResolveAttendanceCorrectionSerializer
)



class EnrolledStudentsForAttendanceView(APIView):
    """
    Returns the enrolled students roster for a specific section and subject,
    along with existing recorded periods for the selected date.
    Enforces that the requesting faculty is assigned or authorized for this class.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_student_role:
            return Response(
                {'detail': 'Students are not authorized to view the attendance marking roster.'},
                status=status.HTTP_403_FORBIDDEN
            )

        section_id = request.query_params.get('section_id')
        subject_id = request.query_params.get('subject_id')
        session_date_str = request.query_params.get('date', timezone.now().date().isoformat())

        if not section_id or not subject_id:
            return Response(
                {'detail': 'Both section_id and subject_id query parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            section = Section.objects.select_related(
                'program__department', 'academic_year', 'academic_class'
            ).get(id=section_id)
        except Section.DoesNotExist:
            return Response({'detail': 'Section not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            subject = Subject.objects.select_related('department').get(id=subject_id)
        except Subject.DoesNotExist:
            return Response({'detail': 'Subject not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Faculty Authorization Check
        is_admin_or_hod = user.is_admin_role or user.is_hod_role
        if not is_admin_or_hod:
            try:
                faculty = user.faculty_profile
                teaches_class = faculty.allocations.filter(
                    section=section, subject=subject, is_active=True
                ).exists()
                is_mentor = (section.mentor == user)
                if not (teaches_class or is_mentor):
                    return Response(
                        {'detail': 'Access denied: You are not allocated to teach this subject in this section.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Faculty.DoesNotExist:
                return Response(
                    {'detail': 'Faculty profile not found for user.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Get students in the section
        students = Student.objects.filter(section=section, user__is_active=True).select_related('user').order_by('roll_number')

        # Check existing sessions for this section + subject on the specified date
        try:
            selected_date = timezone.datetime.strptime(session_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.now().date()

        existing_sessions = AttendanceSession.objects.filter(
            section=section,
            subject=subject,
            session_date=selected_date
        ).values('id', 'period_number', 'session_type', 'status', 'created_at')

        recorded_periods = [s['period_number'] for s in existing_sessions]

        students_data = [
            {
                'id': s.id,
                'user_id': s.user.id,
                'roll_number': s.roll_number,
                'registration_number': s.registration_number,
                'full_name': s.user.get_full_name(),
                'email': s.user.email,
            }
            for s in students
        ]

        return Response({
            'section': {
                'id': section.id,
                'name': section.name,
                'label': str(section),
                'class_name': str(section.academic_class) if section.academic_class else f"{section.program.code} Sem {section.semester}",
                'department': section.program.department.name,
                'semester': section.semester,
            },
            'subject': {
                'id': subject.id,
                'code': subject.code,
                'title': subject.title,
                'credits': subject.credits,
            },
            'selected_date': selected_date.isoformat(),
            'recorded_periods': recorded_periods,
            'existing_sessions': list(existing_sessions),
            'students_count': len(students_data),
            'students': students_data,
        })


class RecordAttendanceBatchView(APIView):
    """
    Submits and atomically commits a batch attendance session with records for all students.
    Validates:
    - Authorization (Faculty allocated or mentor, or Admin/HOD)
    - Future dates prohibited
    - Period bounds (1-7)
    - Duplicate session prevention (section + subject + date + period)
    - Student section membership
    - Creates immutable audit log entries.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # 1. RBAC Validation: Students cannot record attendance
        if user.is_student_role:
            return Response(
                {'detail': 'Students are strictly forbidden from recording attendance.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = BatchAttendanceRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        section = validated_data['section_obj']
        subject = validated_data['subject_obj']
        session_date = validated_data['session_date']
        period_number = validated_data['period_number']
        session_type = validated_data.get('session_type', SessionType.REGULAR)
        topic_covered = validated_data.get('topic_covered', '')
        records_data = validated_data['records']

        # 2. Authorization: Faculty must be allocated or section mentor
        is_admin_or_hod = user.is_admin_role or user.is_hod_role
        if not is_admin_or_hod:
            try:
                faculty = user.faculty_profile
                teaches_class = faculty.allocations.filter(
                    section=section, subject=subject, is_active=True
                ).exists()
                is_mentor = (section.mentor == user)
                if not (teaches_class or is_mentor):
                    return Response(
                        {'detail': 'Access denied: You are not assigned to teach this subject in this section.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Faculty.DoesNotExist:
                return Response(
                    {'detail': 'Faculty profile not found for user.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # 3. Double-check duplicate prevention at atomic boundary
        if AttendanceSession.objects.filter(
            section=section,
            subject=subject,
            session_date=session_date,
            period_number=period_number
        ).exists():
            return Response(
                {'detail': f"Attendance session for {section.name} - {subject.code} on {session_date} Period {period_number} has already been recorded."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Atomic transaction to create session, records, and audit logs
        try:
            with transaction.atomic():
                session = AttendanceSession.objects.create(
                    faculty=user,
                    section=section,
                    subject=subject,
                    session_date=session_date,
                    period_number=period_number,
                    session_type=session_type,
                    status=SessionStatus.SUBMITTED,
                    topic_covered=topic_covered
                )

                created_records = []
                for rec_data in records_data:
                    rec = AttendanceRecord.objects.create(
                        session=session,
                        student_id=rec_data['student_id'],
                        status=rec_data.get('status', AttendanceStatus.PRESENT),
                        remarks=rec_data.get('remarks', '')
                    )
                    created_records.append(rec)

                # Create audit logs
                ip_addr = request.META.get('REMOTE_ADDR')
                audit_logs = [
                    AttendanceAuditLog(
                        record=rec,
                        action=AuditAction.SESSION_CREATED,
                        previous_status='',
                        new_status=rec.status,
                        changed_by=user,
                        reason=f"Attendance submitted for Period {period_number}",
                        ip_address=ip_addr
                    )
                    for rec in created_records
                ]
                AttendanceAuditLog.objects.bulk_create(audit_logs)

        except Exception as e:
            return Response(
                {'detail': f"Failed to record attendance: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Return session detail with deterministic counts and percentage
        session_detail = AttendanceSessionDetailSerializer(session).data
        return Response(
            {
                'message': 'Attendance recorded successfully.',
                'session': session_detail,
                'stats': {
                    'total_students': session.total_students,
                    'present_count': session.present_count,
                    'absent_count': session.absent_count,
                    'late_count': session.late_count,
                    'on_duty_count': session.on_duty_count,
                    'medical_count': session.medical_count,
                    'attendance_percentage': session.attendance_percentage,
                }
            },
            status=status.HTTP_201_CREATED
        )


class AttendanceHistoryListView(generics.ListAPIView):
    """
    Returns attendance sessions history, filterable by:
    - section_id
    - subject_id
    - session_date / start_date / end_date
    - period_number
    Role-based scoping ensures students only see sessions for their section,
    faculty see sessions they conducted or teach, and admins see all.
    """
    serializer_class = AttendanceSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = AttendanceSession.objects.select_related(
            'faculty', 'section__program__department', 'subject'
        ).prefetch_related('records').all()

        # Scoping based on Role
        if user.is_student_role:
            try:
                student = user.student_profile
                qs = qs.filter(section=student.section)
            except Student.DoesNotExist:
                return qs.none()
        elif not (user.is_admin_role or user.is_hod_role):
            # Faculty
            qs = qs.filter(
                faculty=user
            ) | qs.filter(
                section__allocations__faculty__user=user
            ) | qs.filter(
                section__mentor=user
            )
            qs = qs.distinct()

        # Filtering parameters
        section_id = self.request.query_params.get('section_id')
        if section_id:
            qs = qs.filter(section_id=section_id)

        subject_id = self.request.query_params.get('subject_id')
        if subject_id:
            qs = qs.filter(subject_id=subject_id)

        date_str = self.request.query_params.get('date')
        if date_str:
            qs = qs.filter(session_date=date_str)

        start_date = self.request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(session_date__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(session_date__lte=end_date)

        period = self.request.query_params.get('period')
        if period:
            qs = qs.filter(period_number=period)

        return qs.order_by('-session_date', '-period_number')


class AttendanceSessionDetailView(generics.RetrieveAPIView):
    """
    Retrieves full details of a specific attendance session, including
    the student-by-student attendance records and deterministic summary metrics.
    """
    queryset = AttendanceSession.objects.select_related(
        'faculty', 'section__program__department', 'subject'
    ).prefetch_related('records__student__user').all()
    serializer_class = AttendanceSessionDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        session = super().get_object()
        user = self.request.user

        # Access check
        if user.is_student_role:
            try:
                student = user.student_profile
                if session.section != student.section:
                    self.permission_denied(self.request, message="You can only view attendance for your section.")
            except Student.DoesNotExist:
                self.permission_denied(self.request, message="Student profile missing.")
        elif not (user.is_admin_role or user.is_hod_role):
            # Faculty
            is_faculty = (
                session.faculty == user or
                session.section.allocations.filter(faculty__user=user).exists() or
                session.section.mentor == user
            )
            if not is_faculty:
                self.permission_denied(self.request, message="You are not authorized to view this session.")

        return session


class AttendanceRecordListView(generics.ListAPIView):
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = AttendanceRecord.objects.select_related('student__user', 'session__subject').all()

        if user.is_student_role:
            try:
                student = user.student_profile
                qs = qs.filter(student=student)
            except Student.DoesNotExist:
                return qs.none()

        session_id = self.request.query_params.get('session_id')
        if session_id:
            qs = qs.filter(session_id=session_id)

        student_id = self.request.query_params.get('student_id')
        if student_id and not user.is_student_role:
            qs = qs.filter(student_id=student_id)

        return qs


class AttendanceCorrectionListView(APIView):
    """
    GET: List correction requests, strictly scoped to user role.
    POST: Submit a new attendance correction request.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .services import AttendanceCorrectionService
        filters = {}
        if request.query_params.get('status'):
            filters['status'] = request.query_params.get('status')
        if request.query_params.get('record_id'):
            filters['record_id'] = request.query_params.get('record_id')
        if request.query_params.get('student_id'):
            filters['student_id'] = request.query_params.get('student_id')

        qs = AttendanceCorrectionService.get_scoped_corrections(request.user, filters)
        serializer = AttendanceCorrectionSerializer(qs, many=True)
        return Response({
            'count': len(serializer.data),
            'results': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CreateAttendanceCorrectionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        from .services import AttendanceCorrectionService
        from django.core.exceptions import ValidationError, PermissionDenied
        data = serializer.validated_data
        try:
            correction = AttendanceCorrectionService.request_correction(
                record_id=data['record_id'],
                requested_by=request.user,
                requested_status=data['requested_status'],
                reason=data['reason'],
                document_url=data.get('document_url', '')
            )
            out_serializer = AttendanceCorrectionSerializer(correction)
            return Response({
                'message': 'Attendance correction request submitted successfully.',
                'correction': out_serializer.data
            }, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'detail': e.messages if hasattr(e, 'messages') else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)


class AttendanceCorrectionDetailView(APIView):
    """
    GET: Retrieve details of a specific correction request.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from .services import AttendanceCorrectionService
        correction = get_object_or_404(
            AttendanceCorrection.objects.select_related(
                'record__student__user', 'record__session__subject', 'record__session__section',
                'requested_by', 'reviewed_by'
            ),
            id=pk
        )
        user = request.user
        if user.is_student_role:
            if correction.record.student.user != user and correction.requested_by != user:
                return Response({'detail': 'You are not authorized to view this correction request.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = AttendanceCorrectionSerializer(correction)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ApproveAttendanceCorrectionView(APIView):
    """
    POST: Approves an attendance correction request.
    Updates the historical attendance record and creates an immutable AttendanceAuditLog entry.
    Only authorized faculty/mentors/admins can approve (Students are strictly rejected).
    """
    permission_classes = [IsAuthenticated]

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def post(self, request, pk):
        from .services import AttendanceCorrectionService
        from django.core.exceptions import ValidationError, PermissionDenied

        serializer = ResolveAttendanceCorrectionSerializer(data=request.data)
        serializer.is_valid()
        review_notes = serializer.validated_data.get('review_notes', '')

        try:
            correction = AttendanceCorrectionService.approve_correction(
                correction_id=pk,
                reviewed_by=request.user,
                review_notes=review_notes,
                ip_address=self.get_client_ip(request)
            )
            out_serializer = AttendanceCorrectionSerializer(correction)
            return Response({
                'message': f"Correction #{pk} approved successfully. Historical attendance record reconciled.",
                'correction': out_serializer.data
            }, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({'detail': e.messages if hasattr(e, 'messages') else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)


class RejectAttendanceCorrectionView(APIView):
    """
    POST: Rejects an attendance correction request.
    Historical attendance record remains unaltered.
    Emits an immutable AttendanceAuditLog entry documenting the rejection decision.
    Only authorized faculty/mentors/admins can reject.
    """
    permission_classes = [IsAuthenticated]

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def post(self, request, pk):
        from .services import AttendanceCorrectionService
        from django.core.exceptions import ValidationError, PermissionDenied

        serializer = ResolveAttendanceCorrectionSerializer(data=request.data)
        serializer.is_valid()
        review_notes = serializer.validated_data.get('review_notes', '')

        try:
            correction = AttendanceCorrectionService.reject_correction(
                correction_id=pk,
                reviewed_by=request.user,
                review_notes=review_notes,
                ip_address=self.get_client_ip(request)
            )
            out_serializer = AttendanceCorrectionSerializer(correction)
            return Response({
                'message': f"Correction #{pk} rejected. Attendance record remains unaltered.",
                'correction': out_serializer.data
            }, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({'detail': e.messages if hasattr(e, 'messages') else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)


class AttendanceAuditLogListView(APIView):
    """
    GET: List audit trail entries, scoped to user role.
    Shows who changed what, previous status, new status, timestamp, and rationale.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .services import AttendanceCorrectionService
        filters = {}
        if request.query_params.get('record_id'):
            filters['record_id'] = request.query_params.get('record_id')
        if request.query_params.get('student_id'):
            filters['student_id'] = request.query_params.get('student_id')
        if request.query_params.get('action'):
            filters['action'] = request.query_params.get('action')

        qs = AttendanceCorrectionService.get_scoped_audit_logs(request.user, filters)
        serializer = AttendanceAuditLogSerializer(qs, many=True)
        return Response({
            'count': len(serializer.data),
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class RecordAuditHistoryView(APIView):
    """
    GET: Retrieve full audit timeline for a specific attendance record.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, record_id):
        record = get_object_or_404(
            AttendanceRecord.objects.select_related('student__user', 'session__subject'),
            id=record_id
        )
        user = request.user
        if user.is_student_role and record.student.user != user:
            return Response({'detail': 'You can only view audit logs for your own attendance.'}, status=status.HTTP_403_FORBIDDEN)

        from .services import AttendanceCorrectionService
        qs = AttendanceCorrectionService.get_scoped_audit_logs(user, {'record_id': record_id})
        serializer = AttendanceAuditLogSerializer(qs, many=True)
        return Response({
            'record_id': record.id,
            'student_roll': record.student.roll_number,
            'current_status': record.status,
            'subject_code': record.session.subject.code,
            'session_date': record.session.session_date,
            'audit_trail': serializer.data
        }, status=status.HTTP_200_OK)



class StudentMyAttendanceSummaryView(APIView):
    """
    Returns the comprehensive, deterministic attendance calculation summary
    for the logged-in student (or for a specified student if requested by Faculty/Mentor/Admin).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        target_student_id = request.query_params.get('student_id')

        if target_student_id and (user.is_admin_role or user.is_hod_role or user.is_faculty_role or user.is_mentor_role):
            student = get_object_or_404(Student, id=target_student_id)
        elif user.is_student_role:
            try:
                student = user.student_profile
            except Student.DoesNotExist:
                return Response({'detail': 'Student profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response(
                {'detail': 'A valid student_id query parameter is required for administrative/faculty lookup.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from .services import AttendanceCalculationService
        summary = AttendanceCalculationService.calculate_student_overall_attendance(student)
        return Response(summary, status=status.HTTP_200_OK)


class SectionAttendanceAnalyticsView(APIView):
    """
    Returns cohort-level attendance analytics for a specific section and optional subject.
    Scoped to allocated faculty, section mentors, HODs, and administrators.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, section_id):
        user = request.user
        section = get_object_or_404(Section, id=section_id)

        # Scoping verification
        is_authorized = user.is_admin_role or user.is_hod_role or (section.mentor == user)
        if not is_authorized and user.is_faculty_role:
            try:
                is_authorized = user.faculty_profile.allocations.filter(section=section, is_active=True).exists()
            except Faculty.DoesNotExist:
                is_authorized = False

        if not is_authorized:
            return Response(
                {'detail': 'Access denied: You are not authorized to view section analytics.'},
                status=status.HTTP_403_FORBIDDEN
            )

        subject_id = request.query_params.get('subject_id')
        subject = None
        if subject_id:
            subject = get_object_or_404(Subject, id=subject_id)

        from .services import AttendanceCalculationService
        analytics = AttendanceCalculationService.calculate_section_attendance_summary(section, subject=subject)
        return Response(analytics, status=status.HTTP_200_OK)


class AttendancePolicyConfigView(APIView):
    """
    Manages institutional attendance threshold policy.
    GET: Returns active threshold policy (default 75.00%).
    PUT/PATCH: Allows administrators to configure default and condonation thresholds.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        policy = AttendancePolicy.get_active_policy()
        return Response({
            'id': policy.id,
            'institution_name': policy.institution_name,
            'default_threshold': float(policy.default_threshold),
            'condonation_threshold': float(policy.condonation_threshold),
            'warning_buffer_pct': float(policy.warning_buffer_pct),
            'is_active': policy.is_active,
            'updated_at': policy.updated_at,
            'updated_by_name': policy.updated_by.get_full_name() if policy.updated_by else None,
        })

    def put(self, request):
        if not (request.user.is_admin_role or request.user.is_hod_role):
            return Response({'detail': 'Only administrators can update institutional attendance policy.'}, status=status.HTTP_403_FORBIDDEN)

        from decimal import Decimal
        policy = AttendancePolicy.get_active_policy()
        data = request.data

        if 'default_threshold' in data:
            try:
                policy.default_threshold = Decimal(str(data['default_threshold'])).quantize(Decimal('0.01'))
            except Exception:
                return Response({'detail': 'Invalid default_threshold format.'}, status=status.HTTP_400_BAD_REQUEST)

        if 'condonation_threshold' in data:
            try:
                policy.condonation_threshold = Decimal(str(data['condonation_threshold'])).quantize(Decimal('0.01'))
            except Exception:
                return Response({'detail': 'Invalid condonation_threshold format.'}, status=status.HTTP_400_BAD_REQUEST)

        policy.updated_by = request.user
        policy.save()

        return Response({
            'message': 'Attendance policy updated successfully.',
            'default_threshold': float(policy.default_threshold),
            'condonation_threshold': float(policy.condonation_threshold),
            'updated_at': policy.updated_at,
        }, status=status.HTTP_200_OK)


class LowAttendanceStudentsListView(APIView):
    """
    Returns list of students with low attendance (below configurable threshold, default 75%).
    Filterable by department_id, section_id, subject_id, threshold.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .services import AttendanceCalculationService, get_effective_threshold
        threshold_param = request.query_params.get('threshold')
        threshold = get_effective_threshold(threshold_param)

        filters = {}
        if request.query_params.get('department_id'):
            filters['department_id'] = request.query_params.get('department_id')
        if request.query_params.get('section_id'):
            filters['section_id'] = request.query_params.get('section_id')
        if request.query_params.get('subject_id'):
            filters['subject_id'] = request.query_params.get('subject_id')

        low_students = AttendanceCalculationService.get_low_attendance_students_list(filters=filters, threshold=threshold)
        return Response({
            'threshold_used': float(threshold),
            'count': len(low_students),
            'students': low_students,
        }, status=status.HTTP_200_OK)


class AdminLowAttendanceReportView(APIView):
    """
    Comprehensive institutional attendance report for Dean and Administrative heads.
    """
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        from .services import AttendanceCalculationService, get_effective_threshold
        threshold_param = request.query_params.get('threshold')
        threshold = get_effective_threshold(threshold_param)

        report = AttendanceCalculationService.generate_admin_report(threshold=threshold)
        return Response(report, status=status.HTTP_200_OK)


class FacultyLowAttendanceReportView(APIView):
    """
    Scoped low-attendance report for classes taught or mentored by the requesting faculty member.
    """
    permission_classes = [IsFacultyUserRole]

    def get(self, request):
        from .services import AttendanceCalculationService, get_effective_threshold
        threshold_param = request.query_params.get('threshold')
        threshold = get_effective_threshold(threshold_param)

        report = AttendanceCalculationService.generate_faculty_report(request.user, threshold=threshold)
        return Response(report, status=status.HTTP_200_OK)


class StudentAttendanceWarningsView(APIView):
    """
    Returns active low-attendance warnings and required recovery classes for a student.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        target_student_id = request.query_params.get('student_id')

        if target_student_id and (user.is_admin_role or user.is_hod_role or user.is_faculty_role or user.is_mentor_role):
            student = get_object_or_404(Student, id=target_student_id)
        elif user.is_student_role:
            try:
                student = user.student_profile
            except Student.DoesNotExist:
                return Response({'detail': 'Student profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response(
                {'detail': 'A valid student_id query parameter is required for administrative/faculty lookup.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from .services import AttendanceCalculationService, get_effective_threshold
        threshold_param = request.query_params.get('threshold')
        threshold = get_effective_threshold(threshold_param)

        warnings = AttendanceCalculationService.generate_student_warnings(student, threshold=threshold)
        return Response({
            'student_id': student.id,
            'roll_number': student.roll_number,
            'full_name': student.user.get_full_name(),
            'threshold_used': float(threshold),
            'warnings_count': len(warnings),
            'has_active_warnings': len(warnings) > 0,
            'warnings': warnings,
        }, status=status.HTTP_200_OK)


class AdminDashboardOverviewView(APIView):
    """
    Returns full institutional dashboard metrics for Dean & Admin:
    - Total students
    - Total faculty
    - Departments
    - Overall attendance
    - Low attendance students
    - Attendance by department
    - Attendance trends
    """
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        from .services import AttendanceCalculationService, get_effective_threshold
        threshold_param = request.query_params.get('threshold')
        threshold = get_effective_threshold(threshold_param)

        data = AttendanceCalculationService.get_admin_dashboard_summary(threshold=threshold)
        return Response(data, status=status.HTTP_200_OK)


class FacultyDashboardOverviewView(APIView):
    """
    Returns class and section dashboard metrics for Faculty:
    - Today's classes
    - Pending attendance
    - Class attendance
    - Low attendance students
    """
    permission_classes = [IsFacultyUserRole]

    def get(self, request):
        from .services import AttendanceCalculationService, get_effective_threshold
        threshold_param = request.query_params.get('threshold')
        threshold = get_effective_threshold(threshold_param)

        data = AttendanceCalculationService.get_faculty_dashboard_summary(request.user, threshold=threshold)
        return Response(data, status=status.HTTP_200_OK)


class StudentDashboardOverviewView(APIView):
    """
    Returns personalized academic attendance metrics for Student Dashboard:
    - Overall attendance
    - Subject-wise attendance
    - Attendance history
    - Low attendance warnings
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        target_student_id = request.query_params.get('student_id')

        if target_student_id and (user.is_admin_role or user.is_hod_role or user.is_faculty_role or user.is_mentor_role):
            student = get_object_or_404(Student, id=target_student_id)
            student_user = student.user
        elif user.is_student_role:
            try:
                _ = user.student_profile
                student_user = user
            except Student.DoesNotExist:
                return Response({'detail': 'Student profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response(
                {'detail': 'A valid student_id query parameter is required for administrative/faculty lookup.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from .services import AttendanceCalculationService, get_effective_threshold
        threshold_param = request.query_params.get('threshold')
        threshold = get_effective_threshold(threshold_param)

        data = AttendanceCalculationService.get_student_dashboard_summary(student_user, threshold=threshold)
        return Response(data, status=status.HTTP_200_OK)



