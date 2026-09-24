from rest_framework import serializers
from .models import User, Role


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'role_display', 'phone', 'avatar',
            'department', 'department_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class LoginResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    token = serializers.CharField()
