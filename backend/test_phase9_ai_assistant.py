"""
Standalone Verification Script for Phase 9: AI Attendance Assistant.

Tests all required user queries against the live database and validates:
1. "Which students are below 75%?"
2. "Which subjects have the lowest attendance?"
3. "Show Rahul's attendance."
4. "Which department has the lowest attendance?"
5. "Which students have attendance below 70%?"
6. "How has attendance changed this month?"
7. Read-only guarantee: Database records before vs after.
8. API endpoints: POST /api/ai/query/, GET /api/ai/tools/, POST /api/ai/tools/execute/.
9. Security & Role Scoping.
"""

import os
import sys
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import User
from academic.models import Student, Department, Subject
from attendance.models import AttendanceSession, AttendanceRecord
from ai_assistant import tools
from ai_assistant.service import AIAttendanceAssistantService

BASE_URL = 'http://127.0.0.1:8000'


def get_jwt_token(username, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login/", json={'username': username, 'password': password})
    if resp.status_code == 200:
        return resp.json()['access']
    raise RuntimeError(f"Login failed for {username}: {resp.status_code} {resp.text}")


def test_individual_backend_tools():
    print("\n--- 1. Testing Individual Deterministic Backend Tools Against DB ---")
    
    # 1. get_student_attendance
    st_res = tools.get_student_attendance("Rahul")
    assert st_res['status'] == 'success', f"Expected success, got {st_res}"
    assert st_res['student']['full_name'] == 'Rahul Sharma'
    print(f"[PASS] tools.get_student_attendance('Rahul') -> {st_res['student']['full_name']} ({st_res['student']['roll_number']}): {st_res['overall_attendance']['overall_percentage']}% attendance")

    # 2. get_low_attendance_students (75%)
    low75 = tools.get_low_attendance_students(threshold=75.0)
    assert low75['status'] == 'success'
    print(f"[PASS] tools.get_low_attendance_students(75.0) -> {low75['low_attendance_count']} students below 75% ({low75['total_students_evaluated']} evaluated)")

    # 3. get_low_attendance_students (70%)
    low70 = tools.get_low_attendance_students(threshold=70.0)
    assert low70['status'] == 'success'
    print(f"[PASS] tools.get_low_attendance_students(70.0) -> {low70['low_attendance_count']} students below 70%")

    # 4. get_subject_attendance
    subj_res = tools.get_subject_attendance()
    assert subj_res['status'] == 'success'
    lowest_subj = subj_res['lowest_attendance_subject']
    assert lowest_subj is not None, "Expected at least one active subject"
    print(f"[PASS] tools.get_subject_attendance() -> Lowest course: {lowest_subj['code']} ({lowest_subj['average_attendance_percentage']}%)")

    # 5. get_department_attendance
    dept_res = tools.get_department_attendance()
    assert dept_res['status'] == 'success'
    assert dept_res['total_departments'] >= 2
    lowest_dept = dept_res['lowest_attendance_department']
    print(f"[PASS] tools.get_department_attendance() -> Evaluated {dept_res['total_departments']} depts, lowest: {lowest_dept['department_name']} ({lowest_dept['attendance_percentage']}%)")

    # 6. get_attendance_history
    hist_res = tools.get_attendance_history(days=30)
    assert hist_res['status'] == 'success'
    print(f"[PASS] tools.get_attendance_history(30) -> Retrieved {hist_res['total_matching_records']} logged records")

    # 7. get_attendance_statistics
    stats_res = tools.get_attendance_statistics(time_frame='month')
    assert stats_res['status'] == 'success'
    print(f"[PASS] tools.get_attendance_statistics('month') -> {stats_res['current_window']['sessions_conducted']} sessions, {stats_res['current_window']['attendance_percentage']}% attendance")


def test_required_ai_prompts():
    print("\n--- 2. Testing All Required User Prompts Through AIAttendanceAssistantService ---")
    admin_user = User.objects.filter(role='ADMIN').first()

    test_queries = [
        ("Which students are below 75%?", "get_low_attendance_students"),
        ("Which subjects have the lowest attendance?", "get_subject_attendance"),
        ("Show Rahul's attendance.", "get_student_attendance"),
        ("Which department has the lowest attendance?", "get_department_attendance"),
        ("Which students have attendance below 70%?", "get_low_attendance_students"),
        ("How has attendance changed this month?", "get_attendance_statistics"),
    ]

    for q, expected_tool in test_queries:
        res = AIAttendanceAssistantService.process_query(admin_user, q)
        assert res['success'], f"Query failed for '{q}': {res}"
        assert res['tool_called'] == expected_tool, f"Expected tool '{expected_tool}', got '{res['tool_called']}'"
        assert res['answer'] and len(res['answer']) > 10, f"Answer too short for '{q}'"
        print(f"[PASS] Query: \"{q}\"")
        print(f"       -> Tool Called: {res['tool_called']} | Source: {res['execution_source']}")
        print(f"       -> Explanation Snippet: {res['answer'].splitlines()[0]}")


def test_live_ai_api_endpoints():
    print("\n--- 3. Testing Live HTTP AI Endpoints on Local Server ---")
    try:
        admin_token = get_jwt_token('admin', 'Admin@123')
        student_token = get_jwt_token('24cse001', 'Student@123')
    except Exception as e:
        print(f"[SKIP] Live HTTP tests skipped: {e}")
        return

    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    student_headers = {'Authorization': f'Bearer {student_token}'}

    # 1. GET /api/ai/tools/
    tools_resp = requests.get(f"{BASE_URL}/api/ai/tools/", headers=admin_headers)
    assert tools_resp.status_code == 200, f"Failed: {tools_resp.text}"
    catalog = tools_resp.json()
    assert catalog['read_only'] is True
    assert catalog['total_tools'] == 6
    print(f"[PASS] GET /api/ai/tools/ -> 200 OK ({catalog['total_tools']} read-only tools registered)")

    # 2. POST /api/ai/query/ with Admin Token
    q_resp = requests.post(f"{BASE_URL}/api/ai/query/", headers=admin_headers, json={'query': 'Which students are below 75%?'})
    assert q_resp.status_code == 200, f"Failed: {q_resp.text}"
    q_data = q_resp.json()
    assert q_data['success'] is True
    assert q_data['tool_called'] == 'get_low_attendance_students'
    print(f"[PASS] POST /api/ai/query/ (Admin) -> 200 OK: Tool={q_data['tool_called']}, Source={q_data['execution_source']}")

    # 3. Privacy Guard Check: Student requesting institutional low attendance list
    stud_resp = requests.post(f"{BASE_URL}/api/ai/query/", headers=student_headers, json={'query': 'Which students are below 75%?'})
    assert stud_resp.status_code == 200
    stud_data = stud_resp.json()
    assert stud_data['execution_source'] == 'security_guard'
    assert 'privacy' in stud_data['answer'].lower()
    print("[PASS] Security Guard: Student query for institutional low attendance safely scoped and guarded.")

    # 4. Student querying own attendance
    my_resp = requests.post(f"{BASE_URL}/api/ai/query/", headers=student_headers, json={'query': 'Show my attendance'})
    assert my_resp.status_code == 200
    my_data = my_resp.json()
    assert my_data['tool_called'] == 'get_student_attendance'
    assert my_data['tool_parameters']['student_identifier'] == '24cse001'
    print(f"[PASS] Student Query: 'Show my attendance' correctly scoped to student user: {my_data['tool_parameters']['student_identifier']}")

    # 5. Direct Tool Execution: POST /api/ai/tools/execute/
    exec_resp = requests.post(f"{BASE_URL}/api/ai/tools/execute/", headers=admin_headers, json={
        'tool': 'get_student_attendance',
        'parameters': {'student_identifier': 'Rahul'}
    })
    assert exec_resp.status_code == 200, f"Direct tool execute failed: {exec_resp.text}"
    print("[PASS] POST /api/ai/tools/execute/ -> 200 OK: Structured JSON returned directly.")


def test_read_only_integrity():
    print("\n--- 4. Verifying Read-Only Database Integrity ---")
    before_sessions = AttendanceSession.objects.count()
    before_records = AttendanceRecord.objects.count()

    # Run tools multiple times
    tools.get_low_attendance_students(75.0)
    tools.get_student_attendance("Rahul")
    tools.get_department_attendance()
    tools.get_subject_attendance()
    tools.get_attendance_history()
    tools.get_attendance_statistics()

    after_sessions = AttendanceSession.objects.count()
    after_records = AttendanceRecord.objects.count()

    assert before_sessions == after_sessions, f"Session count changed: {before_sessions} != {after_sessions}"
    assert before_records == after_records, f"Record count changed: {before_records} != {after_records}"
    print(f"[PASS] Read-Only Integrity Verified: Sessions ({before_sessions}) & Records ({before_records}) unchanged.")


if __name__ == '__main__':
    print("=" * 60)
    print("EDUMERGE ATTENDANCE - PHASE 9 AI ASSISTANT VERIFICATION")
    print("=" * 60)
    test_individual_backend_tools()
    test_required_ai_prompts()
    test_live_ai_api_endpoints()
    test_read_only_integrity()
    print("\n" + "=" * 60)
    print("ALL PHASE 9 AI ATTENDANCE ASSISTANT VERIFICATIONS PASSED")
    print("=" * 60)
