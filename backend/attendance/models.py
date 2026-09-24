from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SessionStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    LOCKED = 'LOCKED', 'Locked'


class SessionType(models.TextChoices):
    REGULAR = 'REGULAR', 'Regular Lecture'
    LAB = 'LAB', 'Laboratory Session'
    TUTORIAL = 'TUTORIAL', 'Tutorial'
    REMEDIAL = 'REMEDIAL', 'Remedial / Extra Class'


class AttendanceStatus(models.TextChoices):
    PRESENT = 'PRESENT', 'Present'
    ABSENT = 'ABSENT', 'Absent'
    LATE = 'LATE', 'Late Arrival'
    ON_DUTY = 'ON_DUTY', 'On Duty (Authorized)'
    MEDICAL_LEAVE = 'MEDICAL_LEAVE', 'Medical Leave (Authorized)'


class AttendanceSession(models.Model):
    """
    A single conducted lecture or period session for which attendance is recorded.
    Enforces atomic uniqueness, future-date prevention, and period boundaries.
    """
    timetable_slot = models.ForeignKey(
        'academic.TimetableSlot',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_sessions',
        help_text="Optional link to recurring weekly timetable schedule"
    )
    faculty = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='conducted_sessions',
        help_text="Instructor who conducted and marked the attendance"
    )
    section = models.ForeignKey(
        'academic.Section',
        on_delete=models.PROTECT,
        related_name='attendance_sessions'
    )
    subject = models.ForeignKey(
        'academic.Subject',
        on_delete=models.PROTECT,
        related_name='attendance_sessions'
    )
    session_date = models.DateField(default=timezone.now, db_index=True)
    period_number = models.PositiveSmallIntegerField(default=1)
    session_type = models.CharField(
        max_length=20,
        choices=SessionType.choices,
        default=SessionType.REGULAR
    )
    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.SUBMITTED
    )
    topic_covered = models.TextField(blank=True, default='')
    is_locked = models.BooleanField(
        default=False,
        help_text="Locks after 24 hours or administrative cutoff to enforce audit rules"
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-session_date', '-period_number']
        unique_together = ('section', 'subject', 'session_date', 'period_number')
        indexes = [
            models.Index(fields=['section', 'session_date']),
            models.Index(fields=['subject', 'session_date']),
            models.Index(fields=['faculty', 'session_date']),
        ]

    def __str__(self):
        return f"{self.subject.code} - {self.section} ({self.session_date} P{self.period_number})"

    def clean(self):
        # Validation 1: Future dates blocked
        allowed_today = max(timezone.localdate(), timezone.now().date())
        if self.session_date and self.session_date > allowed_today:
            raise ValidationError({'session_date': "Cannot record attendance for future dates."})

        # Validation 2: Period bounds
        if self.period_number < 1 or self.period_number > 7:
            raise ValidationError({'period_number': "Period number must be between 1 and 7."})

        # Validation 3: Semester consistency between subject and section
        if self.subject_id and self.section_id:
            if self.subject.semester != self.section.semester:
                raise ValidationError({
                    'subject': f"Subject {self.subject.code} (Semester {self.subject.semester}) does not match Section {self.section} (Semester {self.section.semester})."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def total_students(self):
        return self.records.count()

    @property
    def present_count(self):
        return self.records.filter(status=AttendanceStatus.PRESENT).count()

    @property
    def absent_count(self):
        return self.records.filter(status=AttendanceStatus.ABSENT).count()

    @property
    def late_count(self):
        return self.records.filter(status=AttendanceStatus.LATE).count()

    @property
    def on_duty_count(self):
        return self.records.filter(status=AttendanceStatus.ON_DUTY).count()

    @property
    def medical_count(self):
        return self.records.filter(status=AttendanceStatus.MEDICAL_LEAVE).count()

    @property
    def attendance_percentage(self):
        """
        Deterministic calculation:
        (Present + Late + OnDuty + Medical) / Total * 100
        Zero-division safe.
        """
        total = self.total_students
        if total == 0:
            return 0.0
        effective_present = (
            self.present_count +
            self.late_count +
            self.on_duty_count +
            self.medical_count
        )
        return round((effective_present / total) * 100, 2)


class AttendanceRecord(models.Model):
    """
    Individual attendance state of a student for a specific session.
    Unique constraint ensures no student can have conflicting records in one session.
    """
    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name='records'
    )
    student = models.ForeignKey(
        'academic.Student',
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
        db_index=True
    )
    remarks = models.CharField(max_length=255, blank=True, default='')
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student__roll_number']
        unique_together = ('session', 'student')
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['session', 'status']),
        ]

    def __str__(self):
        return f"{self.student.roll_number} - {self.session.subject.code}: {self.get_status_display()}"

    def clean(self):
        # Validation: Student must belong to the session's section
        if self.student_id and self.session_id:
            if self.student.section_id != self.session.section_id:
                raise ValidationError({
                    'student': f"Student {self.student.roll_number} belongs to {self.student.section}, not {self.session.section}."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class CorrectionStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Review'
    APPROVED = 'APPROVED', 'Approved & Reconciled'
    REJECTED = 'REJECTED', 'Rejected'


class AttendanceCorrection(models.Model):
    """
    Formal dispute/correction request initiated by a student or teacher,
    supporting documentary proof attachments and multi-tier approval routing.
    """
    record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.CASCADE,
        related_name='corrections'
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='requested_corrections'
    )
    old_status = models.CharField(max_length=20, choices=AttendanceStatus.choices)
    requested_status = models.CharField(max_length=20, choices=AttendanceStatus.choices)
    reason = models.TextField(help_text="Detailed justification (e.g. Sports tournament, Dengue fever hospitalization)")
    document_url = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="Evidence URL or simulated certificate attachment path"
    )
    status = models.CharField(
        max_length=20,
        choices=CorrectionStatus.choices,
        default=CorrectionStatus.PENDING,
        db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_corrections'
    )
    review_notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Correction #{self.id} for {self.record.student.roll_number}: {self.old_status} -> {self.requested_status} ({self.status})"


class AuditAction(models.TextChoices):
    SESSION_CREATED = 'SESSION_CREATED', 'Initial Attendance Recorded'
    SESSION_EDITED = 'SESSION_EDITED', 'Teacher In-Window Edit'
    CORRECTION_APPROVED = 'CORRECTION_APPROVED', 'Correction Workflow Approved'
    CORRECTION_REJECTED = 'CORRECTION_REJECTED', 'Correction Workflow Rejected'
    ADMIN_OVERRIDE = 'ADMIN_OVERRIDE', 'Administrative Policy Override'



class AttendanceAuditLog(models.Model):
    """
    Append-only immutable audit trail capturing every state modification
    to an attendance record, ensuring full statutory compliance and traceability.
    """
    record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=30, choices=AuditAction.choices)
    previous_status = models.CharField(max_length=20, blank=True, default='')
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='attendance_audit_entries'
    )
    reason = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['record', 'timestamp']),
            models.Index(fields=['changed_by', 'timestamp']),
        ]

    def __str__(self):
        return f"AuditLog [{self.timestamp:%Y-%m-%d %H:%M}] {self.record.student.roll_number}: {self.previous_status} -> {self.new_status} by {self.changed_by}"


class AttendancePolicy(models.Model):
    """
    Configurable institutional attendance threshold policy.
    Governs statutory minimum attendance for examinations, condonation limits,
    and automatic warning thresholds.
    """
    institution_name = models.CharField(max_length=150, default="Edumerge Institute of Technology")
    default_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('75.00'),
        help_text="Standard statutory minimum percentage for exam eligibility (default 75.00%)"
    )
    condonation_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('65.00'),
        help_text="Minimum threshold required for condonation consideration (default 65.00%)"
    )
    warning_buffer_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        help_text="Buffer percentage above threshold to trigger proactive warnings (e.g. 75-80%)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='updated_attendance_policies'
    )

    class Meta:
        verbose_name_plural = 'Attendance Policies'
        ordering = ['-is_active', '-updated_at']

    def __str__(self):
        return f"Attendance Policy ({self.default_threshold}% Floor - {'Active' if self.is_active else 'Archived'})"

    @classmethod
    def get_active_policy(cls):
        policy = cls.objects.filter(is_active=True).first()
        if not policy:
            policy = cls.objects.create(
                institution_name="Edumerge Institute of Technology",
                default_threshold=Decimal('75.00'),
                condonation_threshold=Decimal('65.00'),
                is_active=True
            )
        return policy

