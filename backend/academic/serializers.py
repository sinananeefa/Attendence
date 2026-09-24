from rest_framework import serializers
from .models import (
    Department, Program, AcademicYear, Semester, AcademicClass, Section,
    Subject, Student, Faculty, FacultyAllocation, CourseEnrollment, TimetableSlot
)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'


class ProgramSerializer(serializers.ModelSerializer):
    department_code = serializers.CharField(source='department.code', read_only=True)

    class Meta:
        model = Program
        fields = '__all__'


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = '__all__'


class SemesterSerializer(serializers.ModelSerializer):
    term_display = serializers.CharField(source='get_term_display', read_only=True)
    academic_year_label = serializers.CharField(source='academic_year.year_label', read_only=True)

    class Meta:
        model = Semester
        fields = '__all__'


class AcademicClassSerializer(serializers.ModelSerializer):
    program_code = serializers.CharField(source='program.code', read_only=True)
    academic_year_label = serializers.CharField(source='academic_year.year_label', read_only=True)

    class Meta:
        model = AcademicClass
        fields = '__all__'


class SectionSerializer(serializers.ModelSerializer):
    program_code = serializers.CharField(source='program.code', read_only=True)
    mentor_name = serializers.CharField(source='mentor.get_full_name', read_only=True, default='')

    class Meta:
        model = Section
        fields = '__all__'


class SubjectSerializer(serializers.ModelSerializer):
    department_code = serializers.CharField(source='department.code', read_only=True)
    program_code = serializers.CharField(source='program.code', read_only=True, default=None)

    class Meta:
        model = Subject
        fields = '__all__'

    def validate(self, attrs):
        program = attrs.get('program')
        department = attrs.get('department')
        semester = attrs.get('semester')

        if program and department and program.department != department:
            raise serializers.ValidationError({
                'program': f"Selected program '{program.code}' belongs to department '{program.department.code}', not '{department.code}'."
            })
        if program and semester and semester > program.total_semesters:
            raise serializers.ValidationError({
                'semester': f"Semester {semester} exceeds total semesters ({program.total_semesters}) for program '{program.code}'."
            })
        return attrs


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    section_label = serializers.CharField(source='section.__str__', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'roll_number', 'registration_number', 'full_name',
            'email', 'section', 'section_label', 'current_semester',
            'admission_date', 'guardian_name', 'guardian_phone'
        ]


class FacultySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)

    class Meta:
        model = Faculty
        fields = [
            'id', 'employee_id', 'full_name', 'email',
            'designation', 'department', 'department_code', 'qualification'
        ]


class FacultyAllocationSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source='faculty.user.get_full_name', read_only=True)
    faculty_id = serializers.CharField(source='faculty.employee_id', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_title = serializers.CharField(source='subject.title', read_only=True)
    section_label = serializers.CharField(source='section.__str__', read_only=True)

    class Meta:
        model = FacultyAllocation
        fields = '__all__'

    def validate(self, attrs):
        faculty = attrs.get('faculty')
        subject = attrs.get('subject')
        section = attrs.get('section')
        academic_year = attrs.get('academic_year')

        if faculty and not faculty.user.is_active:
            raise serializers.ValidationError({'faculty': "Cannot assign an inactive faculty account."})

        if subject and section and subject.semester != section.semester:
            raise serializers.ValidationError({
                'subject': f"Subject '{subject.code}' (Semester {subject.semester}) cannot be assigned to Section '{section}' (Semester {section.semester}). Semester mismatch."
            })

        if section and academic_year and section.academic_year != academic_year:
            raise serializers.ValidationError({
                'academic_year': f"Allocation academic year must match Section academic year."
            })

        return attrs


class CourseEnrollmentSerializer(serializers.ModelSerializer):
    student_roll = serializers.CharField(source='student.roll_number', read_only=True)
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_title = serializers.CharField(source='subject.title', read_only=True)
    section_label = serializers.CharField(source='section.__str__', read_only=True)

    class Meta:
        model = CourseEnrollment
        fields = '__all__'

    def validate(self, attrs):
        student = attrs.get('student')
        section = attrs.get('section')
        subject = attrs.get('subject')
        academic_year = attrs.get('academic_year')

        # Rule 1: Student section match
        if student and section and student.section != section:
            raise serializers.ValidationError({
                'section': f"Student '{student.roll_number}' belongs to section '{student.section}', not '{section}'."
            })

        # Rule 2: Subject semester match
        if subject and section and subject.semester != section.semester:
            raise serializers.ValidationError({
                'subject': f"Subject '{subject.code}' is designated for Semester {subject.semester}, but student's cohort is in Semester {section.semester}."
            })

        # Rule 3: Check duplicate enrollment
        if student and subject and academic_year:
            existing = CourseEnrollment.objects.filter(
                student=student,
                subject=subject,
                academic_year=academic_year
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({
                    'subject': f"Student '{student.roll_number}' is already enrolled in subject '{subject.code}' for academic year '{academic_year}'."
                })

        return attrs


class TimetableSlotSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)
    subject_code = serializers.CharField(source='allocation.subject.code', read_only=True)
    subject_title = serializers.CharField(source='allocation.subject.title', read_only=True)
    section_label = serializers.CharField(source='allocation.section.__str__', read_only=True)
    faculty_name = serializers.CharField(source='allocation.faculty.user.get_full_name', read_only=True)

    class Meta:
        model = TimetableSlot
        fields = '__all__'
