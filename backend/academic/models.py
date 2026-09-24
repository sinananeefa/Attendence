from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Department(models.Model):
    """Academic Department (e.g., Computer Science, Mechanical Engineering)"""
    code = models.CharField(max_length=10, unique=True, help_text="e.g. CSE, ECE, MECH")
    name = models.CharField(max_length=120, help_text="Full department title")
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Program(models.Model):
    """Degree program offered by a department (e.g., B.Tech, M.Tech)"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='programs')
    code = models.CharField(max_length=20, unique=True, help_text="e.g. BTECH-CSE")
    name = models.CharField(max_length=120)
    total_semesters = models.PositiveSmallIntegerField(default=8)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} ({self.name})"


class AcademicYear(models.Model):
    """Academic year session (e.g., 2026-2027)"""
    year_label = models.CharField(max_length=20, unique=True, help_text="e.g. 2026-2027")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.year_label

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError({'end_date': "End date must be chronologically after start date."})


class Semester(models.Model):
    """
    Explicit semester term within an academic year (e.g. Semester 4 - Even 2026-2027)
    """
    class TermChoices(models.TextChoices):
        ODD = 'ODD', 'Odd Semester (Fall)'
        EVEN = 'EVEN', 'Even Semester (Spring)'

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='semesters')
    semester_number = models.PositiveSmallIntegerField(help_text="1 to 8")
    term = models.CharField(max_length=10, choices=TermChoices.choices, default=TermChoices.EVEN)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['academic_year', 'semester_number']
        unique_together = ('academic_year', 'semester_number')

    def __str__(self):
        return f"Semester {self.semester_number} ({self.academic_year.year_label} - {self.get_term_display()})"

    def clean(self):
        if self.semester_number < 1 or self.semester_number > 12:
            raise ValidationError({'semester_number': "Semester number must be between 1 and 12."})
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError({'end_date': "End date must be after start date."})


class AcademicClass(models.Model):
    """
    Cohort class grouping (e.g. B.Tech CSE Semester 4 - 2026-2027),
    which is subdivided into Sections (A, B, C).
    """
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='academic_classes')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='academic_classes')
    semester = models.PositiveSmallIntegerField(help_text="1 to 8")

    class Meta:
        ordering = ['program', 'semester']
        unique_together = ('program', 'academic_year', 'semester')
        verbose_name_plural = 'Academic Classes'

    def __str__(self):
        return f"{self.program.code} - Sem {self.semester} ({self.academic_year.year_label})"

    def clean(self):
        if self.semester > self.program.total_semesters:
            raise ValidationError({
                'semester': f"Semester {self.semester} exceeds total semesters ({self.program.total_semesters}) for {self.program.code}."
            })


class Section(models.Model):
    """Class section / cohort division (e.g., B.Tech CSE Semester 4, Section A)"""
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='sections')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='sections')
    semester = models.PositiveSmallIntegerField(help_text="1 to 8")
    name = models.CharField(max_length=10, help_text="Section letter e.g. A, B, C")
    academic_class = models.ForeignKey(
        AcademicClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sections',
        help_text="Optional link to parent class cohort"
    )
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mentored_sections',
        help_text="Faculty member acting as the section mentor / class advisor"
    )
    max_capacity = models.PositiveSmallIntegerField(default=60)

    class Meta:
        ordering = ['program', 'semester', 'name']
        unique_together = ('program', 'academic_year', 'semester', 'name')

    def __str__(self):
        return f"{self.program.code} S{self.semester}-{self.name}"

    def clean(self):
        if self.semester > self.program.total_semesters:
            raise ValidationError({
                'semester': f"Semester {self.semester} exceeds program total ({self.program.total_semesters})."
            })


class Subject(models.Model):
    """
    Curriculum course unit with statutory attendance floors.
    Must belong to the appropriate department and program structure.
    """
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='subjects')
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subjects',
        help_text="Specific degree curriculum this subject is designed for"
    )
    code = models.CharField(max_length=20, unique=True, help_text="e.g. CS401")
    title = models.CharField(max_length=150)
    credits = models.PositiveSmallIntegerField(default=3)
    semester = models.PositiveSmallIntegerField(default=1)
    is_elective = models.BooleanField(default=False)
    min_attendance_pct = models.FloatField(
        default=75.0,
        help_text="Statutory threshold required to sit for semester examinations"
    )
    condonation_min_pct = models.FloatField(
        default=65.0,
        help_text="Lower floor eligible for condonation with approved medical/on-duty proof"
    )

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.title}"

    def clean(self):
        # Validation: Subject structure consistency
        if self.semester < 1:
            raise ValidationError({'semester': "Semester must be at least 1."})
        if self.program:
            if self.semester > self.program.total_semesters:
                raise ValidationError({
                    'semester': f"Subject semester ({self.semester}) exceeds program limit ({self.program.total_semesters})."
                })
            if self.program.department != self.department:
                raise ValidationError({
                    'program': f"Program department ({self.program.department.code}) does not match subject department ({self.department.code})."
                })
        if self.condonation_min_pct > self.min_attendance_pct:
            raise ValidationError({
                'condonation_min_pct': "Condonation floor cannot be higher than statutory minimum attendance."
            })


class Faculty(models.Model):
    """Faculty teaching staff profile"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='faculty_profile'
    )
    employee_id = models.CharField(max_length=20, unique=True, db_index=True)
    designation = models.CharField(max_length=60, default="Assistant Professor")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='faculty_members')
    qualification = models.CharField(max_length=100, blank=True, default="M.Tech")

    class Meta:
        ordering = ['employee_id']
        verbose_name_plural = 'Faculty'

    def __str__(self):
        return f"{self.employee_id} - {self.user.get_full_name() or self.user.username}"


class Student(models.Model):
    """Enrolled student linked to identity and section"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )
    roll_number = models.CharField(max_length=20, unique=True, db_index=True)
    registration_number = models.CharField(max_length=30, unique=True, db_index=True)
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name='students')
    current_semester = models.PositiveSmallIntegerField(default=1)
    admission_date = models.DateField(
        help_text="Crucial for calculating attendance denominator for lateral/late entrants"
    )
    guardian_name = models.CharField(max_length=100, blank=True, default='')
    guardian_phone = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        ordering = ['roll_number']

    def __str__(self):
        return f"{self.roll_number} - {self.user.get_full_name() or self.user.username}"


class FacultyAllocation(models.Model):
    """
    Assignment of a faculty member to teach a subject for a specific section.
    Validation enforces:
    - Faculty cannot be assigned incorrectly (semester mismatch, inactive account).
    - Prevents duplicate assignments.
    """
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='allocations')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='allocations')
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='allocations')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='allocations')
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('faculty', 'subject', 'section', 'academic_year')
        indexes = [
            models.Index(fields=['faculty', 'is_active']),
            models.Index(fields=['section', 'subject']),
        ]

    def __str__(self):
        return f"{self.faculty.employee_id} -> {self.subject.code} ({self.section})"

    def clean(self):
        # Validation 1: Inactive faculty cannot be assigned
        if not self.faculty.user.is_active:
            raise ValidationError({'faculty': f"Faculty {self.faculty.employee_id} account is inactive."})

        # Validation 2: Semester mismatch check (Cannot assign S6 subject to S4 section)
        if self.subject.semester != self.section.semester:
            raise ValidationError({
                'subject': f"Subject {self.subject.code} (Semester {self.subject.semester}) cannot be assigned to Section {self.section} (Semester {self.section.semester}). Semester mismatch."
            })

        # Validation 3: Academic year consistency
        if self.section.academic_year != self.academic_year:
            raise ValidationError({
                'academic_year': f"Allocation academic year ({self.academic_year}) must match Section's academic year ({self.section.academic_year})."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class CourseEnrollment(models.Model):
    """
    Individual course enrollment linking a student to a subject in an academic year.
    Validation enforces:
    - A student cannot be enrolled twice in the same subject/section.
    - Enrollment must match student's current cohort and semester curriculum.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='course_enrollments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='student_enrollments')
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='course_enrollments')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='course_enrollments')
    enrollment_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('student', 'subject', 'academic_year')
        indexes = [
            models.Index(fields=['student', 'academic_year']),
            models.Index(fields=['section', 'subject']),
        ]

    def __str__(self):
        return f"{self.student.roll_number} enrolled in {self.subject.code} ({self.section})"

    def clean(self):
        # Validation 1: Student section must match enrollment section
        if self.student.section != self.section:
            raise ValidationError({
                'section': f"Student {self.student.roll_number} belongs to section {self.student.section}, not {self.section}."
            })

        # Validation 2: Subject semester must match section/student semester
        if self.subject.semester != self.section.semester:
            raise ValidationError({
                'subject': f"Subject {self.subject.code} is for Semester {self.subject.semester}, but student is in Semester {self.section.semester}."
            })

        # Validation 3: Academic year consistency
        if self.section.academic_year != self.academic_year:
            raise ValidationError({
                'academic_year': f"Enrollment year ({self.academic_year}) must match Section year ({self.section.academic_year})."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class DayOfWeek(models.IntegerChoices):
    MONDAY = 1, 'Monday'
    TUESDAY = 2, 'Tuesday'
    WEDNESDAY = 3, 'Wednesday'
    THURSDAY = 4, 'Thursday'
    FRIDAY = 5, 'Friday'
    SATURDAY = 6, 'Saturday'


class TimetableSlot(models.Model):
    """Weekly recurring timetable block for an allocation"""
    allocation = models.ForeignKey(FacultyAllocation, on_delete=models.CASCADE, related_name='timetable_slots')
    day_of_week = models.PositiveSmallIntegerField(choices=DayOfWeek.choices)
    period_number = models.PositiveSmallIntegerField(help_text="1 (e.g. 9:00-9:50) through 7")
    start_time = models.TimeField()
    end_time = models.TimeField()
    room_number = models.CharField(max_length=30, default="CR-101")

    class Meta:
        ordering = ['day_of_week', 'period_number']
        unique_together = ('allocation', 'day_of_week', 'period_number')
        indexes = [
            models.Index(fields=['day_of_week', 'period_number']),
        ]

    def __str__(self):
        return f"{self.get_day_of_week_display()} P{self.period_number} [{self.allocation.subject.code} - {self.allocation.section}]"

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({'end_time': "End time must be after start time."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
