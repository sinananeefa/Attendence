from rest_framework import serializers
from .models import User, Role


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    student_profile = serializers.SerializerMethodField()
    faculty_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'role_display', 'phone', 'avatar',
            'department', 'department_name', 'created_at',
            'student_profile', 'faculty_profile', 'is_active',
        ]
        read_only_fields = ['id', 'created_at']

    def get_student_profile(self, obj):
        if hasattr(obj, 'student_profile'):
            sp = obj.student_profile
            return {
                'id': sp.id,
                'roll_number': sp.roll_number,
                'registration_number': sp.registration_number,
                'section_id': sp.section_id,
                'section_name': str(sp.section) if sp.section else None,
                'current_semester': sp.current_semester,
                'admission_date': str(sp.admission_date),
            }
        return None

    def get_faculty_profile(self, obj):
        if hasattr(obj, 'faculty_profile'):
            fp = obj.faculty_profile
            return {
                'id': fp.id,
                'employee_id': fp.employee_id,
                'designation': fp.designation,
                'department_id': fp.department_id,
                'department_name': fp.department.name if fp.department else None,
                'qualification': fp.qualification,
            }
        return None


class LoginResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    token = serializers.CharField()
