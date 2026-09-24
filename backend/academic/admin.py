from django.contrib import admin
from .models import (
    Department, Program, AcademicYear, Semester, AcademicClass, Section,
    Subject, Faculty, Student, FacultyAllocation, CourseEnrollment, TimetableSlot
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'created_at')
    search_fields = ('code', 'name')
    ordering = ('code',)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'department', 'total_semesters')
    list_filter = ('department',)
    search_fields = ('code', 'name')


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('year_label', 'start_date', 'end_date', 'is_current')
    list_filter = ('is_current',)
    search_fields = ('year_label',)


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('semester_number', 'term', 'academic_year', 'start_date', 'end_date', 'is_active')
    list_filter = ('academic_year', 'term', 'is_active')
    ordering = ('academic_year', 'semester_number')


@admin.register(AcademicClass)
class AcademicClassAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'program', 'semester', 'academic_year')
    list_filter = ('academic_year', 'semester', 'program')


class CourseEnrollmentInline(admin.TabularInline):
    model = CourseEnrollment
    extra = 0
    fields = ('subject', 'academic_year', 'is_active')
    autocomplete_fields = ('subject',)


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'program', 'semester', 'name', 'academic_year', 'mentor', 'max_capacity')
    list_filter = ('academic_year', 'semester', 'program')
    search_fields = ('name', 'program__code')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'department', 'program', 'semester', 'credits', 'is_elective', 'min_attendance_pct', 'condonation_min_pct')
    list_filter = ('department', 'semester', 'is_elective')
    search_fields = ('code', 'title')


class FacultyAllocationInline(admin.TabularInline):
    model = FacultyAllocation
    extra = 0
    fields = ('subject', 'section', 'academic_year', 'is_active')


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'get_full_name', 'department', 'designation')
    list_filter = ('department', 'designation')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name', 'user__email')
    inlines = [FacultyAllocationInline]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Faculty Name'


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('roll_number', 'get_full_name', 'section', 'current_semester', 'admission_date')
    list_filter = ('section__program', 'current_semester', 'section')
    search_fields = ('roll_number', 'registration_number', 'user__first_name', 'user__last_name', 'user__email')
    inlines = [CourseEnrollmentInline]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Student Name'


@admin.register(FacultyAllocation)
class FacultyAllocationAdmin(admin.ModelAdmin):
    list_display = ('faculty', 'subject', 'section', 'academic_year', 'is_active')
    list_filter = ('academic_year', 'is_active', 'subject__department')
    search_fields = ('faculty__employee_id', 'subject__code', 'section__name')


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'section', 'academic_year', 'enrollment_date', 'is_active')
    list_filter = ('academic_year', 'is_active', 'section')
    search_fields = ('student__roll_number', 'subject__code', 'subject__title')


@admin.register(TimetableSlot)
class TimetableSlotAdmin(admin.ModelAdmin):
    list_display = ('allocation', 'day_of_week', 'period_number', 'start_time', 'end_time', 'room_number')
    list_filter = ('day_of_week', 'period_number')
