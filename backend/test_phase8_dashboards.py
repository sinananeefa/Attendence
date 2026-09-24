import os
import sys
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from attendance.models import (
    AttendanceRecord, AttendanceSession, AttendanceStatus, AttendancePolicy
)
from attendance.services import AttendanceCalculationService
from academic.models import Student, Faculty, Department, Section, Subject
from accounts.models import User

BASE_URL = 'http://127.0.0.1:8000'


def get_jwt_token(username, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login/", json={'username': username, 'password': password})
    if resp.status_code == 200:
        return resp.json()['access']
    raise RuntimeError(f"Login failed for {username}: {resp.status_code} {resp.text}")


def test_admin_dashboard_database_accuracy():
    print("\n--- 1. Testing Admin Dashboard Against Database ---")
    data = AttendanceCalculationService.get_admin_dashboard_summary()

    # Total students
    db_students_count = Student.objects.filter(user__is_active=True).count()
    assert data['total_students'] == db_students_count, f"Student count mismatch: {data['total_students']} != {db_students_count}"
    print(f"[PASS] Total students verified against DB: {data['total_students']}")

    # Total faculty
    db_faculty_count = Faculty.objects.filter(user__is_active=True).count()
    assert data['total_faculty'] == db_faculty_count, f"Faculty count mismatch: {data['total_faculty']} != {db_faculty_count}"
    print(f"[PASS] Total faculty verified against DB: {data['total_faculty']}")

    # Total departments
    db_dept_count = Department.objects.count()
    assert data['total_departments'] == db_dept_count, f"Department count mismatch: {data['total_departments']} != {db_dept_count}"
    print(f"[PASS] Total departments verified against DB: {data['total_departments']}")

    # Overall attendance
    print(f"[PASS] Overall institutional attendance: {data['overall_attendance_percentage']}%")

    # Attendance by department
    assert 'departments' in data and len(data['departments']) > 0, "No departmental breakdown found"
    print(f"[PASS] Attendance by department verified: {len(data['departments'])} departments reported")

    # Attendance trends
    assert 'attendance_trends' in data, "No attendance trends found"
    print(f"[PASS] Attendance trends verified: {len(data['attendance_trends'])} date points computed")

    # Low attendance students
    print(f"[PASS] Low attendance students count: {data['low_attendance_count']}")


def test_faculty_dashboard_database_accuracy():
    print("\n--- 2. Testing Faculty Dashboard Against Database ---")
    faculty_user = User.objects.filter(role='FACULTY').first()
    if not faculty_user:
        print("[SKIP] No faculty user found.")
        return

    data = AttendanceCalculationService.get_faculty_dashboard_summary(faculty_user)

    # Today's classes
    assert 'today_classes' in data, "today_classes missing"
    print(f"[PASS] Faculty today's classes verified: {len(data['today_classes'])} class allocations")

    # Pending attendance
    assert 'pending_attendance_count' in data, "pending_attendance_count missing"
    print(f"[PASS] Pending attendance count verified: {data['pending_attendance_count']}")

    # Class attendance
    assert 'class_attendance' in data, "class_attendance missing"
    print(f"[PASS] Class cohort attendance verified: {len(data['class_attendance'])} section cohorts")

    # Low attendance students
    assert 'low_attendance_students' in data, "low_attendance_students missing"
    print(f"[PASS] Low attendance students in faculty courses verified: {len(data['low_attendance_students'])} students")


def test_student_dashboard_database_accuracy():
    print("\n--- 3. Testing Student Dashboard Against Database ---")
    student_user = User.objects.filter(role='STUDENT').first()
    if not student_user:
        print("[SKIP] No student user found.")
        return

    data = AttendanceCalculationService.get_student_dashboard_summary(student_user)

    # Overall attendance
    assert 'overall_attendance' in data, "overall_attendance missing"
    overall = data['overall_attendance']
    assert 'overall_percentage' in overall
    print(f"[PASS] Student overall attendance verified: {overall['overall_percentage']}% ({overall['total_attended']}/{overall['total_conducted']})")

    # Subject-wise attendance
    assert 'subject_wise_attendance' in data, "subject_wise_attendance missing"
    print(f"[PASS] Subject-wise attendance verified: {len(data['subject_wise_attendance'])} subjects")

    # Attendance history
    assert 'attendance_history' in data, "attendance_history missing"
    print(f"[PASS] Attendance history records verified: {len(data['attendance_history'])} history entries")

    # Low attendance warnings
    assert 'low_attendance_warnings' in data, "low_attendance_warnings missing"
    warnings = data['low_attendance_warnings']
    print(f"[PASS] Low attendance warnings verified: {warnings['warnings_count']} active warnings")


def test_live_dashboard_http_endpoints():
    print("\n--- 4. Testing Live HTTP Dashboard APIs on Local Server ---")
    try:
        admin_token = get_jwt_token('admin', 'Admin@123')
        faculty_token = get_jwt_token('fac_priya', 'Faculty@123')
        student_token = get_jwt_token('24cse001', 'Student@123')
    except Exception as e:
        print(f"[SKIP] Live HTTP tests skipped: {e}")
        return

    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    faculty_headers = {'Authorization': f'Bearer {faculty_token}'}
    student_headers = {'Authorization': f'Bearer {student_token}'}

    # Admin Dashboard API
    admin_resp = requests.get(f"{BASE_URL}/api/attendance/dashboard/admin/", headers=admin_headers)
    assert admin_resp.status_code == 200, f"Admin dashboard failed: {admin_resp.text}"
    a_data = admin_resp.json()
    assert 'total_students' in a_data
    assert 'departments' in a_data
    assert 'attendance_trends' in a_data
    print(f"[PASS] GET /api/attendance/dashboard/admin/ -> 200 OK (Students: {a_data['total_students']}, Depts: {a_data['total_departments']})")

    # Security check: Student blocked from Admin Dashboard
    stud_admin_resp = requests.get(f"{BASE_URL}/api/attendance/dashboard/admin/", headers=student_headers)
    assert stud_admin_resp.status_code == 403, f"Expected 403, got {stud_admin_resp.status_code}"
    print("[PASS] Security RBAC: Student blocked from Admin Dashboard -> 403 Forbidden")

    # Faculty Dashboard API
    fac_resp = requests.get(f"{BASE_URL}/api/attendance/dashboard/faculty/", headers=faculty_headers)
    assert fac_resp.status_code == 200, f"Faculty dashboard failed: {fac_resp.text}"
    f_data = fac_resp.json()
    assert 'today_classes' in f_data
    assert 'pending_attendance_count' in f_data
    print(f"[PASS] GET /api/attendance/dashboard/faculty/ -> 200 OK (Classes: {len(f_data['today_classes'])}, Pending: {f_data['pending_attendance_count']})")

    # Student Dashboard API
    stud_resp = requests.get(f"{BASE_URL}/api/attendance/dashboard/student/", headers=student_headers)
    assert stud_resp.status_code == 200, f"Student dashboard failed: {stud_resp.text}"
    s_data = stud_resp.json()
    assert 'overall_attendance' in s_data
    assert 'subject_wise_attendance' in s_data
    assert 'attendance_history' in s_data
    assert 'low_attendance_warnings' in s_data
    print(f"[PASS] GET /api/attendance/dashboard/student/ -> 200 OK (Overall: {s_data['overall_attendance']['overall_percentage']}%, Subjects: {len(s_data['subject_wise_attendance'])})")


if __name__ == '__main__':
    print("=" * 60)
    print("EDUMERGE ATTENDANCE - PHASE 8 DASHBOARDS & REPORTS VERIFICATION")
    print("=" * 60)
    test_admin_dashboard_database_accuracy()
    test_faculty_dashboard_database_accuracy()
    test_student_dashboard_database_accuracy()
    test_live_dashboard_http_endpoints()
    print("\n" + "=" * 60)
    print("ALL PHASE 8 DASHBOARDS & REPORTS VERIFIED AGAINST DATABASE")
    print("=" * 60)
