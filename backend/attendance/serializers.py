from rest_framework import serializers
from django.utils import timezone
from .models import (
    AttendanceSession, AttendanceRecord, AttendanceCorrection, AttendanceAuditLog,
    AttendanceStatus, SessionType, SessionStatus
)
from academic.models import Section, Subject, Student, CourseEnrollment


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_id = serializers.IntegerField(source='student.id', read_only=True)
    student_roll = serializers.CharField(source='student.roll_number', read_only=True)
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'student_id', 'student_roll', 'student_name',
            'status', 'status_display', 'remarks', 'marked_at'
        ]


class AttendanceSessionSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_title = serializers.CharField(source='subject.title', read_only=True)
    section_label = serializers.CharField(source='section.__str__', read_only=True)
    faculty_name = serializers.CharField(source='faculty.get_full_name', read_only=True)
    records_count = serializers.IntegerField(source='records.count', read_only=True)
    total_students = serializers.IntegerField(read_only=True)
    present_count = serializers.IntegerField(read_only=True)
    absent_count = serializers.IntegerField(read_only=True)
    late_count = serializers.IntegerField(read_only=True)
    on_duty_count = serializers.IntegerField(read_only=True)
    medical_count = serializers.IntegerField(read_only=True)
    attendance_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'timetable_slot', 'faculty', 'faculty_name',
            'section', 'section_label', 'subject', 'subject_code', 'subject_title',
            'session_date', 'period_number', 'session_type', 'status',
            'topic_covered', 'is_locked', 'records_count',
            'total_students', 'present_count', 'absent_count',
            'late_count', 'on_duty_count', 'medical_count',
            'attendance_percentage', 'created_at'
        ]


class AttendanceSessionDetailSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source='faculty.get_full_name', read_only=True)
    section_name = serializers.CharField(source='section.__str__', read_only=True)
    department_name = serializers.CharField(source='section.program.department.name', read_only=True)
    department_code = serializers.CharField(source='section.program.department.code', read_only=True)
    academic_class_name = serializers.CharField(source='section.academic_class.__str__', read_only=True, default='')
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_title = serializers.CharField(source='subject.title', read_only=True)
    records = AttendanceRecordSerializer(many=True, read_only=True)
    total_students = serializers.IntegerField(read_only=True)
    present_count = serializers.IntegerField(read_only=True)
    absent_count = serializers.IntegerField(read_only=True)
    late_count = serializers.IntegerField(read_only=True)
    on_duty_count = serializers.IntegerField(read_only=True)
    medical_count = serializers.IntegerField(read_only=True)
    attendance_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'session_date', 'period_number', 'session_type', 'status',
            'topic_covered', 'is_locked', 'created_at',
            'faculty', 'faculty_name',
            'section', 'section_name', 'department_name', 'department_code', 'academic_class_name',
            'subject', 'subject_code', 'subject_title',
            'total_students', 'present_count', 'absent_count',
            'late_count', 'on_duty_count', 'medical_count',
            'attendance_percentage', 'records'
        ]


class AttendanceRecordInputSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    status = serializers.ChoiceField(
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT
    )
    remarks = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default=''
    )


class BatchAttendanceRecordSerializer(serializers.Serializer):
    section_id = serializers.IntegerField()
    subject_id = serializers.IntegerField()
    session_date = serializers.DateField()
    period_number = serializers.IntegerField(min_value=1, max_value=7)
    session_type = serializers.ChoiceField(
        choices=SessionType.choices,
        default=SessionType.REGULAR
    )
    topic_covered = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default=''
    )
    records = AttendanceRecordInputSerializer(many=True)

    def validate_session_date(self, value):
        allowed_today = max(timezone.localdate(), timezone.now().date())
        if value > allowed_today:
            raise serializers.ValidationError("Cannot record attendance for future dates.")
        return value

    def validate_period_number(self, value):
        if value < 1 or value > 7:
            raise serializers.ValidationError("Period number must be between 1 and 7.")
        return value

    def validate(self, data):
        # 1. Verify section and subject exist
        try:
            section = Section.objects.select_related('program__department').get(id=data['section_id'])
        except Section.DoesNotExist:
            raise serializers.ValidationError({'section_id': "Section does not exist."})

        try:
            subject = Subject.objects.select_related('department').get(id=data['subject_id'])
        except Subject.DoesNotExist:
            raise serializers.ValidationError({'subject_id': "Subject does not exist."})

        # 2. Semester consistency
        if subject.semester != section.semester:
            raise serializers.ValidationError({
                'subject_id': f"Subject '{subject.code}' (Semester {subject.semester}) does not match Section '{section}' (Semester {section.semester})."
            })

        # 3. Duplicate session prevention
        duplicate_exists = AttendanceSession.objects.filter(
            section=section,
            subject=subject,
            session_date=data['session_date'],
            period_number=data['period_number']
        ).exists()

        if duplicate_exists:
            raise serializers.ValidationError({
                'non_field_errors': [
                    f"An attendance session already exists for Section '{section.name}', Subject '{subject.code}' on {data['session_date']} Period {data['period_number']}."
                ]
            })

        # 4. Records validation
        records = data.get('records', [])
        if not records:
            raise serializers.ValidationError({'records': "At least one student attendance record must be provided."})

        student_ids = [r['student_id'] for r in records]
        if len(student_ids) != len(set(student_ids)):
            raise serializers.ValidationError({'records': "Duplicate student entries submitted in attendance list."})

        # Check all students exist and belong to section
        valid_students = set(
            Student.objects.filter(id__in=student_ids, section=section).values_list('id', flat=True)
        )
        invalid_ids = set(student_ids) - valid_students
        if invalid_ids:
            raise serializers.ValidationError({
                'records': f"Student IDs {list(invalid_ids)} do not belong to section {section.name}."
            })

        data['section_obj'] = section
        data['subject_obj'] = subject
        return data


class AttendanceCorrectionSerializer(serializers.ModelSerializer):
    student_roll = serializers.CharField(source='record.student.roll_number', read_only=True)
    student_name = serializers.CharField(source='record.student.user.get_full_name', read_only=True)
    subject_code = serializers.CharField(source='record.session.subject.code', read_only=True)
    subject_title = serializers.CharField(source='record.session.subject.title', read_only=True)
    session_date = serializers.DateField(source='record.session.session_date', read_only=True)
    period_number = serializers.IntegerField(source='record.session.period_number', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = AttendanceCorrection
        fields = [
            'id', 'record', 'student_roll', 'student_name', 'subject_code', 'subject_title',
            'session_date', 'period_number',
            'requested_by', 'requested_by_name', 'old_status', 'requested_status',
            'reason', 'document_url', 'status', 'reviewed_by', 'reviewed_by_name',
            'review_notes', 'created_at', 'resolved_at'
        ]


class CreateAttendanceCorrectionSerializer(serializers.Serializer):
    record_id = serializers.IntegerField()
    requested_status = serializers.ChoiceField(choices=AttendanceStatus.choices)
    reason = serializers.CharField(min_length=5, max_length=1000)
    document_url = serializers.CharField(required=False, allow_blank=True, default='')


class ResolveAttendanceCorrectionSerializer(serializers.Serializer):
    review_notes = serializers.CharField(required=False, allow_blank=True, default='')


class AttendanceAuditLogSerializer(serializers.ModelSerializer):
    student_roll = serializers.CharField(source='record.student.roll_number', read_only=True)
    student_name = serializers.CharField(source='record.student.user.get_full_name', read_only=True)
    subject_code = serializers.CharField(source='record.session.subject.code', read_only=True)
    session_date = serializers.DateField(source='record.session.session_date', read_only=True)
    changed_by_name = serializers.CharField(source='changed_by.get_full_name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = AttendanceAuditLog
        fields = [
            'id', 'record', 'student_roll', 'student_name', 'subject_code', 'session_date',
            'action', 'action_display', 'previous_status', 'new_status',
            'changed_by', 'changed_by_name', 'reason', 'ip_address', 'timestamp'
        ]

