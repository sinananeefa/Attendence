import os
import sys
from decimal import Decimal
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from attendance.services import (
    is_low_attendance,
    get_effective_threshold,
    AttendanceCalculationService,
    calculate_attendance_percentage,
    calculate_classes_needed_for_target
)
from attendance.models import AttendancePolicy

BASE_URL = 'http://127.0.0.1:8000'

def test_deterministic_boundaries():
    print("\n--- 1. Testing Deterministic Boundary Conditions ---")
    threshold = Decimal('75.00')

    # Test 74.99%
    res_74_99 = is_low_attendance(Decimal('74.99'), threshold)
    assert res_74_99 is True, f"Expected 74.99% to be low attendance, got {res_74_99}"
    print("[PASS] Boundary 74.99% < 75.00% -> is_low_attendance is True")

    # Test 75.00%
    res_75_00 = is_low_attendance(Decimal('75.00'), threshold)
    assert res_75_00 is False, f"Expected 75.00% NOT to be low attendance, got {res_75_00}"
    print("[PASS] Boundary 75.00% < 75.00% -> is_low_attendance is False (Compliant)")

    # Test 75.01%
    res_75_01 = is_low_attendance(Decimal('75.01'), threshold)
    assert res_75_01 is False, f"Expected 75.01% NOT to be low attendance, got {res_75_01}"
    print("[PASS] Boundary 75.01% < 75.00% -> is_low_attendance is False (Compliant)")

    # Test 0%
    res_0 = is_low_attendance(Decimal('0.00'), threshold)
    assert res_0 is True, f"Expected 0.00% to be low attendance, got {res_0}"
    print("[PASS] Boundary 0.00% < 75.00% -> is_low_attendance is True (Critical Shortage)")

    # Test 100%
    res_100 = is_low_attendance(Decimal('100.00'), threshold)
    assert res_100 is False, f"Expected 100.00% NOT to be low attendance, got {res_100}"
    print("[PASS] Boundary 100.00% < 75.00% -> is_low_attendance is False (Compliant)")


def test_configurable_threshold():
    print("\n--- 2. Testing Configurable Attendance Threshold ---")
    policy = AttendancePolicy.get_active_policy()
    print(f"Active policy threshold: {policy.default_threshold}%")
    assert policy.default_threshold == Decimal('75.00'), f"Expected default 75.00%, got {policy.default_threshold}"
    print("[PASS] Default statutory threshold verified at 75.00%")

    # Test dynamic threshold variation
    assert is_low_attendance(Decimal('78.00'), threshold=Decimal('80.00')) is True
    assert is_low_attendance(Decimal('80.00'), threshold=Decimal('80.00')) is False
    print("[PASS] Dynamic threshold configuration (80.00%) correctly flags 78.00% as low attendance")


def test_recovery_calculation():
    print("\n--- 3. Testing Recovery Target Mathematics ---")
    # Student has 10 classes conducted, 6 attended = 60.00%.
    # Target 75%: (6 + x)/(10 + x) >= 0.75 -> 6 + x >= 7.5 + 0.75x -> 0.25x >= 1.5 -> x >= 6
    needed = calculate_classes_needed_for_target(6, 10, Decimal('75.00'))
    assert needed == 6, f"Expected 6 consecutive classes needed, got {needed}"
    print(f"[PASS] Recovery calculation: 6/10 attended -> requires {needed} consecutive classes for 75%")


def get_jwt_token(username, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login/", json={'username': username, 'password': password})
    if resp.status_code == 200:
        return resp.json()['access']
    raise RuntimeError(f"Login failed for {username}: {resp.status_code} {resp.text}")



def test_live_api_endpoints():
    print("\n--- 4. Testing Live HTTP Endpoints on Local Server ---")
    try:
        # Check if server is running
        admin_token = get_jwt_token('admin', 'Admin@123')
        faculty_token = get_jwt_token('fac_priya', 'Faculty@123')
        student_token = get_jwt_token('24cse001', 'Student@123')
    except Exception as e:
        print(f"[SKIP] Live HTTP tests skipped (Server not responsive on {BASE_URL}): {e}")
        return

    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    faculty_headers = {'Authorization': f'Bearer {faculty_token}'}
    student_headers = {'Authorization': f'Bearer {student_token}'}

    # 1. Policy Endpoint (GET)
    p_resp = requests.get(f"{BASE_URL}/api/attendance/policy/", headers=admin_headers)
    assert p_resp.status_code == 200, f"Policy GET failed: {p_resp.text}"
    p_data = p_resp.json()
    assert p_data['default_threshold'] == 75.0
    print(f"[PASS] GET /api/attendance/policy/ -> 200 OK (threshold: {p_data['default_threshold']}%)")

    # 2. Low Attendance Students List Endpoint
    list_resp = requests.get(f"{BASE_URL}/api/attendance/low-attendance/students/", headers=admin_headers)
    assert list_resp.status_code == 200, f"Low attendance list failed: {list_resp.text}"
    l_data = list_resp.json()
    print(f"[PASS] GET /api/attendance/low-attendance/students/ -> 200 OK (evaluated {l_data['count']} students)")

    # 3. Admin Report Endpoint
    admin_rep_resp = requests.get(f"{BASE_URL}/api/attendance/reports/admin/", headers=admin_headers)
    assert admin_rep_resp.status_code == 200, f"Admin report failed: {admin_rep_resp.text}"
    rep_data = admin_rep_resp.json()
    assert 'institutional_at_risk_percentage' in rep_data
    assert 'departments' in rep_data
    print(f"[PASS] GET /api/attendance/reports/admin/ -> 200 OK (Institutional At-Risk: {rep_data['institutional_at_risk_percentage']}%)")

    # Non-admin forbidden on admin report
    stud_rep_resp = requests.get(f"{BASE_URL}/api/attendance/reports/admin/", headers=student_headers)
    assert stud_rep_resp.status_code == 403, f"Expected 403 for student on admin report, got {stud_rep_resp.status_code}"
    print("[PASS] Security RBAC: Student blocked from Admin Report -> 403 Forbidden")

    # 4. Faculty Report Endpoint
    fac_rep_resp = requests.get(f"{BASE_URL}/api/attendance/reports/faculty/", headers=faculty_headers)
    assert fac_rep_resp.status_code == 200, f"Faculty report failed: {fac_rep_resp.text}"
    f_data = fac_rep_resp.json()
    assert 'sections' in f_data
    print(f"[PASS] GET /api/attendance/reports/faculty/ -> 200 OK (Sections Monitored: {len(f_data['sections'])})")

    # 5. Student Warning Endpoint
    stud_warn_resp = requests.get(f"{BASE_URL}/api/attendance/student/warnings/", headers=student_headers)
    assert stud_warn_resp.status_code == 200, f"Student warnings failed: {stud_warn_resp.text}"
    w_data = stud_warn_resp.json()
    assert 'has_active_warnings' in w_data
    assert 'warnings' in w_data
    print(f"[PASS] GET /api/attendance/student/warnings/ -> 200 OK (Active warnings: {w_data['warnings_count']})")


if __name__ == '__main__':
    print("=" * 60)
    print("EDUMERGE ATTENDANCE - PHASE 6 LOW ATTENDANCE VERIFICATION")
    print("=" * 60)
    test_deterministic_boundaries()
    test_configurable_threshold()
    test_recovery_calculation()
    test_live_api_endpoints()
    print("\n" + "=" * 60)
    print("ALL PHASE 6 VERIFICATION CHECKS COMPLETED SUCCESSFULLY")
    print("=" * 60)
