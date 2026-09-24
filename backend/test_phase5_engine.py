import os
import sys
import urllib.request
import urllib.parse
import json
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

BASE_URL = 'http://127.0.0.1:8000/api'

def make_request(url, method='GET', data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    body = json.dumps(data).encode('utf-8') if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode('utf-8')
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode('utf-8')
        try:
            return e.code, json.loads(content)
        except Exception:
            return e.code, {'detail': content}

def login(username, password):
    status, res = make_request(f'{BASE_URL}/auth/login/', method='POST', data={
        'username': username, 'password': password
    })
    if status != 200:
        raise Exception(f"Login failed for {username}: {res}")
    return res['access'], res['user']

def run_tests():
    print("==================================================")
    print("PHASE 5: ATTENDANCE CALCULATION ENGINE VERIFICATION")
    print("==================================================")

    # ----------------------------------------------------
    # PART 1: PURE DECIMAL ARITHMETIC UNIT CHECKS
    # ----------------------------------------------------
    from attendance.services import (
        calculate_attendance_percentage,
        calculate_classes_needed_for_target,
        calculate_classes_can_afford_to_miss,
        get_attendance_status_category,
        AttendanceStatusCategory
    )

    # 1. 0 classes conducted handling
    zero_classes_res = calculate_attendance_percentage(0, 0)
    assert zero_classes_res == Decimal('0.00'), f"Expected 0.00, got {zero_classes_res}"
    print(f"[PASS] 1. Zero Conducted Classes Handled Safely: calculate_attendance_percentage(0, 0) = {zero_classes_res}% (No division by zero)")

    # 2. 100% attendance handling
    p100_1 = calculate_attendance_percentage(1, 1)
    p100_10 = calculate_attendance_percentage(10, 10)
    p100_45 = calculate_attendance_percentage(45, 45)
    assert p100_1 == Decimal('100.00') and p100_10 == Decimal('100.00') and p100_45 == Decimal('100.00')
    print(f"[PASS] 2. 100% Attendance Verified: 1/1 = {p100_1}%, 10/10 = {p100_10}%, 45/45 = {p100_45}%")

    # 3. 0% attendance handling
    p0_1 = calculate_attendance_percentage(0, 1)
    p0_10 = calculate_attendance_percentage(0, 10)
    p0_50 = calculate_attendance_percentage(0, 50)
    assert p0_1 == Decimal('0.00') and p0_10 == Decimal('0.00') and p0_50 == Decimal('0.00')
    print(f"[PASS] 3. 0% Attendance Verified: 0/1 = {p0_1}%, 0/10 = {p0_10}%, 0/50 = {p0_50}%")

    # 4. Partial attendance & Exact Decimal Rounding (ROUND_HALF_UP)
    p_1_3 = calculate_attendance_percentage(1, 3)  # 33.333... -> 33.33
    p_2_3 = calculate_attendance_percentage(2, 3)  # 66.666... -> 66.67
    p_3_4 = calculate_attendance_percentage(3, 4)  # 75.00
    p_7_8 = calculate_attendance_percentage(7, 8)  # 87.50
    p_1_6 = calculate_attendance_percentage(1, 6)  # 16.666... -> 16.67
    p_5_6 = calculate_attendance_percentage(5, 6)  # 83.333... -> 83.33
    p_1_7 = calculate_attendance_percentage(1, 7)  # 14.285... -> 14.29
    p_29_33 = calculate_attendance_percentage(29, 33)  # 87.878... -> 87.88

    assert p_1_3 == Decimal('33.33'), f"Expected 33.33, got {p_1_3}"
    assert p_2_3 == Decimal('66.67'), f"Expected 66.67, got {p_2_3}"
    assert p_3_4 == Decimal('75.00'), f"Expected 75.00, got {p_3_4}"
    assert p_7_8 == Decimal('87.50'), f"Expected 87.50, got {p_7_8}"
    assert p_1_6 == Decimal('16.67'), f"Expected 16.67, got {p_1_6}"
    assert p_5_6 == Decimal('83.33'), f"Expected 83.33, got {p_5_6}"
    assert p_1_7 == Decimal('14.29'), f"Expected 14.29, got {p_1_7}"
    assert p_29_33 == Decimal('87.88'), f"Expected 87.88, got {p_29_33}"

    print(f"[PASS] 4. Partial Attendance & Decimal Precision Verified: 1/3={p_1_3}%, 2/3={p_2_3}%, 7/8={p_7_8}%, 29/33={p_29_33}%")

    # 5. Invalid parameters raise ValueError
    try:
        calculate_attendance_percentage(-1, 5)
        assert False, "Should have raised ValueError for negative attended"
    except ValueError:
        pass

    try:
        calculate_attendance_percentage(5, -1)
        assert False, "Should have raised ValueError for negative conducted"
    except ValueError:
        pass

    try:
        calculate_attendance_percentage(6, 5)
        assert False, "Should have raised ValueError for attended > conducted"
    except ValueError:
        pass
    print("[PASS] 5. Boundary & Integrity Guards Verified (Negative & Overflow inputs correctly raise ValueError)")

    # 6. Predictive Calculations: Classes Needed to Reach 75%
    # If 5 attended of 10 (50%), needs 10 consecutive classes: (5+10)/(10+10) = 15/20 = 75.0%
    needed_5_10 = calculate_classes_needed_for_target(5, 10, Decimal('75.00'))
    assert needed_5_10 == 10, f"Expected 10, got {needed_5_10}"

    # If 8 attended of 10 (80%), already >= 75%, needs 0
    needed_8_10 = calculate_classes_needed_for_target(8, 10, Decimal('75.00'))
    assert needed_8_10 == 0, f"Expected 0, got {needed_8_10}"
    print(f"[PASS] 6. Target Recovery Projection Verified: 5/10 attended needs {needed_5_10} consecutive classes to reach 75%")

    # 7. Predictive Calculations: Classes Can Afford to Miss
    # If 30 attended of 30 (100%), can miss 10 classes: 30 / 40 = 75.0%
    buffer_30 = calculate_classes_can_afford_to_miss(30, 30, Decimal('75.00'))
    assert buffer_30 == 10, f"Expected 10, got {buffer_30}"

    # If 8 attended of 10 (80%), can miss 0 classes (8/11 = 72.7% < 75%)
    buffer_8_10 = calculate_classes_can_afford_to_miss(8, 10, Decimal('75.00'))
    assert buffer_8_10 == 0, f"Expected 0, got {buffer_8_10}"
    print(f"[PASS] 7. Safe Buffer Projection Verified: 30/30 attended can afford to miss {buffer_30} classes while staying >= 75%")

    # ----------------------------------------------------
    # PART 2: LIVE REST API VERIFICATION
    # ----------------------------------------------------

    # 8. Student Live API: GET /api/attendance/student/my-summary/
    student_token, student_user = login('24cse001', 'Student@123')
    status, student_summary = make_request(f'{BASE_URL}/attendance/student/my-summary/', token=student_token)
    assert status == 200, f"Expected 200, got {status}: {student_summary}"

    assert 'overall_percentage' in student_summary
    assert 'total_conducted' in student_summary
    assert 'total_attended' in student_summary
    assert 'total_missed' in student_summary
    assert 'subjects' in student_summary
    assert len(student_summary['subjects']) > 0

    print(f"[PASS] 8. Live Student Attendance Summary API Verified:")
    print(f"     Student: {student_summary['full_name']} ({student_summary['roll_number']})")
    print(f"     Overall Attendance: {student_summary['total_attended']}/{student_summary['total_conducted']} Conducted = {student_summary['overall_percentage']}%")
    print(f"     Compliance Status: {student_summary['overall_status']}")
    print(f"     Enrolled Subjects Evaluated: {len(student_summary['subjects'])}")

    # 9. Verify Subject-Wise breakdown in student response
    first_sub = student_summary['subjects'][0]
    assert 'subject_code' in first_sub
    assert 'classes_conducted' in first_sub
    assert 'classes_attended' in first_sub
    assert 'classes_missed' in first_sub
    assert 'attendance_percentage' in first_sub
    assert 'status' in first_sub
    assert 'classes_needed_for_75' in first_sub
    assert 'classes_can_miss_for_75' in first_sub

    # Verify mathematical identity: conducted == attended + missed
    for s in student_summary['subjects']:
        assert s['classes_conducted'] == s['classes_attended'] + s['classes_missed'], \
            f"Math identity failed: {s['classes_conducted']} != {s['classes_attended']} + {s['classes_missed']}"

    print(f"[PASS] 9. Subject-Wise Attendance Breakdown Verified: Mathematical identity (Conducted = Attended + Missed) holds for all subjects")

    # 10. Faculty Live API: GET /api/attendance/analytics/section/1/
    faculty_token, faculty_user = login('fac_priya', 'Faculty@123')
    status, section_analytics = make_request(f'{BASE_URL}/attendance/analytics/section/1/', token=faculty_token)
    assert status == 200, f"Expected 200, got {status}: {section_analytics}"

    assert 'class_average_percentage' in section_analytics
    assert 'distribution' in section_analytics
    assert 'students' in section_analytics
    assert len(section_analytics['students']) > 0

    print(f"[PASS] 10. Section Cohort Analytics API Verified:")
    print(f"     Section: {section_analytics['section_label']} ({section_analytics['total_students']} Students)")
    print(f"     Class Average: {section_analytics['class_average_percentage']}%")
    print(f"     Distribution: >=75%: {section_analytics['distribution']['eligible_above_75']}, 65-75%: {section_analytics['distribution']['condonation_65_to_75']}, <65%: {section_analytics['distribution']['critical_below_65']}")

    print("==================================================")
    print("ALL 10 PHASE 5 CALCULATION ENGINE TESTS PASSED!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
