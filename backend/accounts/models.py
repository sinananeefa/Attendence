from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = 'ADMIN', 'Dean / Institutional Admin'
    HOD = 'HOD', 'Head of Department'
    FACULTY = 'FACULTY', 'Subject Teacher'
    MENTOR = 'MENTOR', 'Class Mentor'
    STUDENT = 'STUDENT', 'Student'


class User(AbstractUser):
    """
    Custom user model supporting unified institutional identity
    with granular role-based access control.
    """
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True,
        help_text="Primary institutional role for permissions and navigation"
    )
    phone = models.CharField(max_length=20, blank=True, default='')
    avatar = models.CharField(max_length=255, blank=True, default='')
    department = models.ForeignKey(
        'academic.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text="Affiliated department for HOD, faculty, or students"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['username']
        indexes = [
            models.Index(fields=['role', 'department']),
        ]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN or self.is_superuser

    @property
    def is_hod_role(self):
        return self.role == Role.HOD

    @property
    def is_faculty_role(self):
        return self.role in [Role.FACULTY, Role.HOD, Role.MENTOR]

    @property
    def is_mentor_role(self):
        return self.role == Role.MENTOR

    @property
    def is_student_role(self):
        return self.role == Role.STUDENT
