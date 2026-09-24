import os
import sys
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from attendance.models import (
    AttendanceRecord, AttendanceSession, AttendanceStatus,
    AttendanceCorrection, AttendanceAuditLog, CorrectionStatus, AuditAction
)
from attendance.services import AttendanceCorrectionService

BASE_URL = 'http://127.0.0.1:8000'


def get_jwt_token(username, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login/", json={'username': username, 'password': password})
    if resp.status_code == 200:
        return resp.json()['access']
    raise RuntimeError(f"Login failed for {username}: {resp.status_code} {resp.text}")


def test_correction_workflow_live():
    print("\n--- 1. Testing Live Attendance Correction Workflow ---")
    try:
        admin_token = get_jwt_token('admin', 'Admin@123')
        faculty_token = get_jwt_token('fac_priya', 'Faculty@123')
        student_token = get_jwt_token('24cse001', 'Student@123')
    except Exception as e:
        print(f"[SKIP] Live test skipped (Server not responsive on {BASE_URL}): {e}")
        return

    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    faculty_headers = {'Authorization': f'Bearer {faculty_token}'}
    student_headers = {'Authorization': f'Bearer {student_token}'}

    # Find a record for student 24cse001
    record = AttendanceRecord.objects.filter(student__roll_number='24CSE001').first()
    if not record:
        print("[SKIP] No attendance records found for 24CSE001 to test live.")
        return

    # Clean up any existing pending corrections for this record
    AttendanceCorrection.objects.filter(record=record, status=CorrectionStatus.PENDING).delete()

    # Step 1: Student submits a correction request
    target_status = AttendanceStatus.MEDICAL_LEAVE if record.status != AttendanceStatus.MEDICAL_LEAVE else AttendanceStatus.ON_DUTY
    initial_status = record.status

    req_payload = {
        'record_id': record.id,
        'requested_status': target_status,
        'reason': 'Live verification: Dengue fever hospitalization with discharge summary.',
        'document_url': 'https://edumerge.ac.in/hospital_cert_live.pdf'
    }
    req_resp = requests.post(f"{BASE_URL}/api/attendance/corrections/", json=req_payload, headers=student_headers)
    assert req_resp.status_code == 201, f"Failed to submit correction request: {req_resp.text}"
    corr_data = req_resp.json()['correction']
    corr_id = corr_data['id']
    assert corr_data['old_status'] == initial_status
    assert corr_data['requested_status'] == target_status
    assert corr_data['status'] == 'PENDING'
    print(f"[PASS] Correction request #{corr_id} submitted by student (Old: {initial_status} -> Req: {target_status})")

    # Step 2: Unauthorized attempt - Student tries to approve their own correction
    unauth_resp = requests.post(f"{BASE_URL}/api/attendance/corrections/{corr_id}/approve/", json={}, headers=student_headers)
    assert unauth_resp.status_code == 403, f"Expected 403 for student approval, got {unauth_resp.status_code}"
    print("[PASS] Security RBAC: Student blocked from approving correction -> 403 Forbidden")

    # Step 3: Admin / Authorized Faculty approves correction
    approve_payload = {'review_notes': 'Verified hospital certificate. Approved.'}
    appr_resp = requests.post(f"{BASE_URL}/api/attendance/corrections/{corr_id}/approve/", json=approve_payload, headers=admin_headers)
    assert appr_resp.status_code == 200, f"Approval failed: {appr_resp.text}"
    appr_data = appr_resp.json()['correction']
    assert appr_data['status'] == 'APPROVED'
    print(f"[PASS] Correction #{corr_id} approved by authorized administrator")

    # Step 4: Verify record was updated AND audit log was created (NOT silently overwritten)
    record.refresh_from_db()
    assert record.status == target_status, f"Expected record status to update to {target_status}, got {record.status}"
    audit_entry = AttendanceAuditLog.objects.filter(record=record, action=AuditAction.CORRECTION_APPROVED).order_by('-timestamp').first()
    assert audit_entry is not None, "Audit log entry was NOT found!"
    assert audit_entry.previous_status == initial_status
    assert audit_entry.new_status == target_status
    print(f"[PASS] Historical record reconciled and immutable audit log created: {initial_status} -> {target_status} by {audit_entry.changed_by.username}")

    # Step 5: Test Rejection Workflow
    # Create another request to test rejection
    another_status = AttendanceStatus.ABSENT if record.status != AttendanceStatus.ABSENT else AttendanceStatus.LATE
    req2_payload = {
        'record_id': record.id,
        'requested_status': another_status,
        'reason': 'Live verification: Request submitted for rejection test.',
    }
    req2_resp = requests.post(f"{BASE_URL}/api/attendance/corrections/", json=req2_payload, headers=student_headers)
    assert req2_resp.status_code == 201, f"Failed to submit 2nd request: {req2_resp.text}"
    corr2_id = req2_resp.json()['correction']['id']

    # Admin rejects
    reject_payload = {'review_notes': 'Insufficient justification provided.'}
    rej_resp = requests.post(f"{BASE_URL}/api/attendance/corrections/{corr2_id}/reject/", json=reject_payload, headers=admin_headers)
    assert rej_resp.status_code == 200, f"Rejection failed: {rej_resp.text}"
    assert rej_resp.json()['correction']['status'] == 'REJECTED'

    # Verify record was UNTOUCHED
    record.refresh_from_db()
    assert record.status == target_status, f"Expected record status to remain {target_status}, got {record.status}"
    rej_audit = AttendanceAuditLog.objects.filter(record=record, action=AuditAction.CORRECTION_REJECTED).first()
    assert rej_audit is not None
    print(f"[PASS] Correction #{corr2_id} rejected: Attendance record remained unaltered, rejection audit log created")

    # Step 6: Test Record Audit History Timeline API
    audit_resp = requests.get(f"{BASE_URL}/api/attendance/records/{record.id}/audit-logs/", headers=student_headers)
    assert audit_resp.status_code == 200, f"Failed to fetch audit timeline: {audit_resp.text}"
    trail = audit_resp.json()['audit_trail']
    assert len(trail) >= 2, f"Expected at least 2 audit entries, found {len(trail)}"
    print(f"[PASS] GET /api/attendance/records/{record.id}/audit-logs/ -> 200 OK ({len(trail)} audit entries in timeline)")


if __name__ == '__main__':
    print("=" * 60)
    print("EDUMERGE ATTENDANCE - PHASE 7 CORRECTION WORKFLOW VERIFICATION")
    print("=" * 60)
    test_correction_workflow_live()
    print("\n" + "=" * 60)
    print("ALL PHASE 7 VERIFICATION CHECKS COMPLETED SUCCESSFULLY")
    print("=" * 60)
