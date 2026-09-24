"""
API Views for AI Attendance Assistant.

Guarantees:
- Strictly Read-Only operations.
- Zero raw SQL execution.
- Enforced authentication and role-based permissions.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .service import AIAttendanceAssistantService
from . import tools


class AIAssistantQueryView(APIView):
    """
    POST /api/ai/query/
    Accepts a natural language query from an authenticated user,
    dispatches the appropriate deterministic backend tool,
    and returns a structured explanation and raw data.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = request.data.get('query')
        if not query or not str(query).strip():
            return Response(
                {'detail': 'Query parameter is required and cannot be empty.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = AIAttendanceAssistantService.process_query(request.user, str(query).strip())
        return Response(result, status=status.HTTP_200_OK)


class AIToolsCatalogView(APIView):
    """
    GET /api/ai/tools/
    Returns catalog of registered read-only backend attendance tools.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        catalog = AIAttendanceAssistantService.list_available_tools()
        return Response({
            'total_tools': len(catalog),
            'read_only': True,
            'tools': catalog
        }, status=status.HTTP_200_OK)


class AIDirectToolExecutionView(APIView):
    """
    POST /api/ai/tools/execute/
    Executes a specific read-only tool directly by name.
    Useful for deterministic API integration and automated validation tests.
    """
    permission_classes = [IsAuthenticated]

    ALLOWED_TOOLS = {
        'get_student_attendance': tools.get_student_attendance,
        'get_low_attendance_students': tools.get_low_attendance_students,
        'get_subject_attendance': tools.get_subject_attendance,
        'get_department_attendance': tools.get_department_attendance,
        'get_attendance_history': tools.get_attendance_history,
        'get_attendance_statistics': tools.get_attendance_statistics,
    }

    def post(self, request):
        tool_name = request.data.get('tool')
        params = request.data.get('parameters', {})

        if not tool_name or tool_name not in self.ALLOWED_TOOLS:
            return Response(
                {
                    'detail': f"Invalid tool name '{tool_name}'. Allowed tools: {list(self.ALLOWED_TOOLS.keys())}",
                    'allowed_tools': list(self.ALLOWED_TOOLS.keys())
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # RBAC Check
        if request.user.role == 'STUDENT':
            if tool_name == 'get_low_attendance_students':
                return Response(
                    {'detail': "Students cannot view institutional low attendance lists."},
                    status=status.HTTP_403_FORBIDDEN
                )
            if tool_name == 'get_student_attendance':
                ident = str(params.get('student_identifier', '')).lower()
                user_name = request.user.username.lower()
                first_name = (request.user.first_name or '').lower()
                if ident not in [user_name, first_name, 'my', 'me']:
                    return Response(
                        {'detail': "Students are only permitted to query their own attendance."},
                        status=status.HTTP_403_FORBIDDEN
                    )
                params['student_identifier'] = request.user.username

        tool_fn = self.ALLOWED_TOOLS[tool_name]
        try:
            result = tool_fn(**params)
            return Response({
                'tool': tool_name,
                'parameters': params,
                'result': result
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'detail': f"Error executing tool '{tool_name}': {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
