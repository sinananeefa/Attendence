import urllib.request
import urllib.parse
import json
import datetime
import sys

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
    print("PHASE 4: ATTENDANCE RECORDING LIVE API TEST SUITE")
    print("==================================================")

    # 1. Login as Faculty (fac_priya - CSE Teacher)
    faculty_token, faculty_user = login('fac_priya', 'Faculty@123')
    print(f"[PASS] 1. Faculty Login Success: {faculty_user['first_name']} {faculty_user['last_name']} (Role: {faculty_user['role']})")

    # 2. Get Faculty Allocations
    status, alloc_data = make_request(f'{BASE_URL}/academic/faculty/my-allocations/', token=faculty_token)
    assert status == 200, f"Expected 200, got {status}: {alloc_data}"
    allocations = alloc_data['allocations']
    assert len(allocations) > 0, "Faculty should have active allocations"
    alloc = allocations[0]
    section_id = alloc['section']
    subject_id = alloc['subject']
    print(f"[PASS] 2. Retrieved Faculty Allocation: {alloc['subject_code']} for Section {alloc['section_label']} (Section ID: {section_id}, Subject ID: {subject_id})")

    # 3. Get Attendance Roster for Section
    today_str = datetime.date.today().isoformat()
    status, roster_data = make_request(
        f'{BASE_URL}/attendance/roster/?section_id={section_id}&subject_id={subject_id}&date={today_str}',
        token=faculty_token
    )
    assert status == 200, f"Expected 200, got {status}: {roster_data}"
    students = roster_data['students']
    assert len(students) >= 2, f"Section should have enrolled students, found {len(students)}"
    print(f"[PASS] 3. Attendance Roster Loaded: {len(students)} Enrolled Students in {roster_data['section']['name']}")

    # Find an unrecorded period for today
    recorded_periods = roster_data['recorded_periods']
    target_period = 1
    for p in range(1, 8):
        if p not in recorded_periods:
            target_period = p
            break

    print(f"     Targeting test submission for Period {target_period} on {today_str}")

    # 4. Submit Batch Attendance Session
    # Mark first student Absent, remaining Present
    records = []
    for idx, st in enumerate(students):
        rec_status = 'ABSENT' if idx == 0 else 'PRESENT'
        records.append({
            'student_id': st['id'],
            'status': rec_status,
            'remarks': 'Sick leave reported' if idx == 0 else ''
        })

    submit_payload = {
        'section_id': section_id,
        'subject_id': subject_id,
        'session_date': today_str,
        'period_number': target_period,
        'session_type': 'REGULAR',
        'topic_covered': 'Phase 4 Verification: Relational Algebra & Indexing',
        'records': records
    }

    status, sub_resp = make_request(f'{BASE_URL}/attendance/record/', method='POST', data=submit_payload, token=faculty_token)
    assert status == 201, f"Expected 201 Created, got {status}: {sub_resp}"
    session_id = sub_resp['session']['id']
    stats = sub_resp['stats']
    total_st = len(students)
    expected_present = total_st - 1
    expected_pct = round((expected_present / total_st) * 100, 2)

    assert stats['total_students'] == total_st, f"Expected {total_st}, got {stats['total_students']}"
    assert stats['present_count'] == expected_present, f"Expected {expected_present}, got {stats['present_count']}"
    assert stats['absent_count'] == 1, f"Expected 1 absent, got {stats['absent_count']}"
    assert stats['attendance_percentage'] == expected_pct, f"Expected {expected_pct}%, got {stats['attendance_percentage']}%"

    print(f"[PASS] 4. Attendance Session #{session_id} Recorded Successfully!")
    print(f"     Deterministic Calculation: {stats['present_count']}/{stats['total_students']} Present = {stats['attendance_percentage']}% (Expected: {expected_pct}%)")

    # 5. Prevent Duplicate Attendance Session
    status, dup_resp = make_request(f'{BASE_URL}/attendance/record/', method='POST', data=submit_payload, token=faculty_token)
    assert status == 400, f"Expected 400 Bad Request for duplicate, got {status}: {dup_resp}"
    print(f"[PASS] 5. Duplicate Prevention Passed: Second submission for Period {target_period} correctly rejected with HTTP 400: {dup_resp}")

    # 6. Test Permissions: Student cannot record attendance
    student_token, student_user = login('24cse001', 'Student@123')
    status, st_resp = make_request(f'{BASE_URL}/attendance/record/', method='POST', data=submit_payload, token=student_token)
    assert status == 403, f"Expected 403 Forbidden for Student, got {status}: {st_resp}"
    print(f"[PASS] 6. Security & RBAC Passed: Student user blocked with HTTP 403 Forbidden: {st_resp['detail']}")

    # 7. Test Permissions: Unallocated faculty cannot record attendance for this class
    unalloc_token, unalloc_user = login('fac_meenakshi', 'Faculty@123')
    unalloc_payload = dict(submit_payload)
    unalloc_payload['period_number'] = 7
    status, unalloc_resp = make_request(f'{BASE_URL}/attendance/record/', method='POST', data=unalloc_payload, token=unalloc_token)
    assert status == 403, f"Expected 403 Forbidden for unallocated faculty, got {status}: {unalloc_resp}"
    print(f"[PASS] 7. Faculty Scoping Passed: Unassigned faculty blocked with HTTP 403 Forbidden: {unalloc_resp['detail']}")

    # 8. Test Invalid Data: Future date rejected
    tomorrow_str = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
    future_payload = dict(submit_payload)
    future_payload['session_date'] = tomorrow_str
    status, fut_resp = make_request(f'{BASE_URL}/attendance/record/', method='POST', data=future_payload, token=faculty_token)
    assert status == 400, f"Expected 400 for future date, got {status}: {fut_resp}"
    print(f"[PASS] 8. Validation Passed: Future date submission rejected with HTTP 400: {fut_resp}")

    # 9. Test Invalid Data: Period out of range
    inv_period_payload = dict(submit_payload)
    inv_period_payload['period_number'] = 9
    status, per_resp = make_request(f'{BASE_URL}/attendance/record/', method='POST', data=inv_period_payload, token=faculty_token)
    assert status == 400, f"Expected 400 for period 9, got {status}: {per_resp}"
    print(f"[PASS] 9. Validation Passed: Period 9 out of bounds rejected with HTTP 400: {per_resp}")

    # 10. Test Attendance History API
    status, hist_data = make_request(
        f'{BASE_URL}/attendance/history/?section_id={section_id}&subject_id={subject_id}',
        token=faculty_token
    )
    assert status == 200, f"Expected 200, got {status}: {hist_data}"
    sessions = hist_data.get('results', hist_data)
    assert len(sessions) > 0, "History should return recorded session"
    recorded_session = next(s for s in sessions if s['id'] == session_id)
    assert recorded_session['attendance_percentage'] == expected_pct
    print(f"[PASS] 10. Attendance History API Verified: Returned {len(sessions)} session(s), percentage verified: {recorded_session['attendance_percentage']}%")

    # 11. Test Single Session Detail API
    status, detail_data = make_request(f'{BASE_URL}/attendance/sessions/{session_id}/', token=faculty_token)
    assert status == 200, f"Expected 200, got {status}: {detail_data}"
    records_in_session = detail_data['records']
    assert len(records_in_session) == total_st
    print(f"[PASS] 11. Attendance Session Detail Verified: {len(records_in_session)} student records with audit log tracking")

    print("==================================================")
    print("ALL 11 PHASE 4 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
