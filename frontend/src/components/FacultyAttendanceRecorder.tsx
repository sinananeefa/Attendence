import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  AttendanceStatus,
  SessionType,
  BatchAttendanceSubmissionPayload,
  AttendanceSession,
  AttendanceRosterResponse,
} from '../types';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Calendar,
  Clock,
  BookOpen,
  Users,
  CheckSquare,
  History,
  Check,
  Send,
  RefreshCw,
  Search,
  Filter,
  FileCheck2,
  AlertCircle
} from 'lucide-react';

interface StudentMarkingState {
  id: number;
  roll_number: string;
  registration_number: string;
  full_name: string;
  email: string;
  status: AttendanceStatus;
  remarks: string;
}

export const FacultyAttendanceRecorder: React.FC = () => {
  // Allocations & Selection State
  const [allocations, setAllocations] = useState<any[]>([]);
  const [selectedAllocationId, setSelectedAllocationId] = useState<number | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [selectedPeriod, setSelectedPeriod] = useState<number>(1);
  const [sessionType, setSessionType] = useState<SessionType>('REGULAR');
  const [topicCovered, setTopicCovered] = useState<string>('');

  // Roster & Attendance Marking State
  const [rosterData, setRosterData] = useState<AttendanceRosterResponse | null>(null);
  const [students, setStudents] = useState<StudentMarkingState[]>([]);
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [isLoadingRoster, setIsLoadingRoster] = useState<boolean>(false);

  // Review Modal & Submission State
  const [isReviewModalOpen, setIsReviewModalOpen] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [submissionSuccess, setSubmissionSuccess] = useState<{
    message: string;
    session: AttendanceSession;
    stats: any;
  } | null>(null);

  // History State
  const [activeSubTab, setActiveSubTab] = useState<'record' | 'history'>('record');
  const [historySessions, setHistorySessions] = useState<AttendanceSession[]>([]);
  const [selectedHistorySession, setSelectedHistorySession] = useState<AttendanceSession | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);

  // 1. Load Faculty Allocations on Mount
  useEffect(() => {
    const loadAllocations = async () => {
      try {
        const data = await api.getFacultyAllocations();
        const allocs = data.allocations || [];
        setAllocations(allocs);
        if (allocs.length > 0) {
          setSelectedAllocationId(allocs[0].id);
        }
      } catch (err: any) {
        console.error('Failed to load faculty allocations:', err);
      }
    };
    loadAllocations();
  }, []);

  // 2. Load Roster whenever Allocation or Date changes
  useEffect(() => {
    if (!selectedAllocationId || allocations.length === 0) return;
    const currentAlloc = allocations.find((a) => a.id === selectedAllocationId);
    if (!currentAlloc) return;

    const loadRoster = async () => {
      setIsLoadingRoster(true);
      setSubmissionError(null);
      setSubmissionSuccess(null);
      try {
        const roster = await api.getAttendanceRoster(
          currentAlloc.section,
          currentAlloc.subject,
          selectedDate
        );
        setRosterData(roster);

        // Initialize students with default PRESENT
        const initialMarking: StudentMarkingState[] = roster.students.map((st) => ({
          ...st,
          status: 'PRESENT',
          remarks: '',
        }));
        setStudents(initialMarking);

        // Auto-select first available period if period 1 is recorded
        if (roster.recorded_periods.includes(selectedPeriod)) {
          const availablePeriods = [1, 2, 3, 4, 5, 6, 7].filter(
            (p) => !roster.recorded_periods.includes(p)
          );
          if (availablePeriods.length > 0) {
            setSelectedPeriod(availablePeriods[0]);
          }
        }
      } catch (err: any) {
        console.error('Failed to load roster:', err);
        setSubmissionError(err.message || 'Failed to load enrolled students roster.');
      } finally {
        setIsLoadingRoster(false);
      }
    };

    loadRoster();
  }, [selectedAllocationId, selectedDate, allocations]);

  // Load History when switching to history tab
  useEffect(() => {
    if (activeSubTab === 'history') {
      loadHistory();
    }
  }, [activeSubTab, selectedAllocationId]);

  const loadHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const currentAlloc = allocations.find((a) => a.id === selectedAllocationId);
      const params: any = {};
      if (currentAlloc) {
        params.section_id = currentAlloc.section;
        params.subject_id = currentAlloc.subject;
      }
      const data = await api.getAttendanceHistory(params);
      setHistorySessions(data);
    } catch (err: any) {
      console.error('Failed to fetch attendance history:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // Current active allocation
  const currentAlloc = allocations.find((a) => a.id === selectedAllocationId);

  // Deterministic Live Metric Calculations
  const totalStudents = students.length;
  const presentCount = students.filter((s) => s.status === 'PRESENT').length;
  const absentCount = students.filter((s) => s.status === 'ABSENT').length;
  const lateCount = students.filter((s) => s.status === 'LATE').length;
  const onDutyCount = students.filter((s) => s.status === 'ON_DUTY').length;
  const medicalCount = students.filter((s) => s.status === 'MEDICAL_LEAVE').length;

  // Formula: (Present + Late + OD + Medical) / Total * 100
  const effectivePresent = presentCount + lateCount + onDutyCount + medicalCount;
  const attendancePercentage = totalStudents > 0
    ? Math.round((effectivePresent / totalStudents) * 10000) / 100
    : 0;

  // Quick Action Handlers
  const handleMarkAllPresent = () => {
    setStudents((prev) => prev.map((s) => ({ ...s, status: 'PRESENT' })));
  };

  const handleMarkAllAbsent = () => {
    setStudents((prev) => prev.map((s) => ({ ...s, status: 'ABSENT' })));
  };

  const handleSetStudentStatus = (studentId: number, status: AttendanceStatus) => {
    setStudents((prev) =>
      prev.map((s) => (s.id === studentId ? { ...s, status } : s))
    );
  };

  const handleSetStudentRemarks = (studentId: number, remarks: string) => {
    setStudents((prev) =>
      prev.map((s) => (s.id === studentId ? { ...s, remarks } : s))
    );
  };

  // Submit Attendance Handler
  const handleSubmitAttendance = async () => {
    if (!currentAlloc) return;
    setIsSubmitting(true);
    setSubmissionError(null);

    const payload: BatchAttendanceSubmissionPayload = {
      section_id: currentAlloc.section,
      subject_id: currentAlloc.subject,
      session_date: selectedDate,
      period_number: selectedPeriod,
      session_type: sessionType,
      topic_covered: topicCovered,
      records: students.map((s) => ({
        student_id: s.id,
        status: s.status,
        remarks: s.remarks,
      })),
    };

    try {
      const response = await api.submitAttendance(payload);
      setSubmissionSuccess(response);
      setIsReviewModalOpen(false);

      // Refresh roster data to update recorded periods
      const updatedRoster = await api.getAttendanceRoster(
        currentAlloc.section,
        currentAlloc.subject,
        selectedDate
      );
      setRosterData(updatedRoster);
    } catch (err: any) {
      setSubmissionError(err.message || 'Failed to submit attendance session.');
      setIsReviewModalOpen(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Filtered Students for Table Search
  const filteredStudents = students.filter(
    (s) =>
      s.roll_number.toLowerCase().includes(searchFilter.toLowerCase()) ||
      s.full_name.toLowerCase().includes(searchFilter.toLowerCase())
  );

  const isPeriodRecorded = rosterData?.recorded_periods.includes(selectedPeriod) || false;
  const absenteesList = students.filter((s) => s.status === 'ABSENT');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Sub Tabs: Record vs History */}
      <div style={{ display: 'flex', gap: '0.75rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
        <button
          onClick={() => setActiveSubTab('record')}
          style={{
            background: activeSubTab === 'record' ? 'rgba(16, 185, 129, 0.2)' : 'transparent',
            border: activeSubTab === 'record' ? '1px solid #10b981' : '1px solid transparent',
            color: activeSubTab === 'record' ? '#6ee7b7' : 'var(--text-muted)',
            padding: '0.5rem 1.1rem',
            borderRadius: 'var(--radius-sm)',
            fontWeight: 700,
            fontSize: '0.875rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            transition: 'all 0.15s',
          }}
        >
          <CheckSquare size={16} />
          Record Attendance
        </button>
        <button
          onClick={() => setActiveSubTab('history')}
          style={{
            background: activeSubTab === 'history' ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
            border: activeSubTab === 'history' ? '1px solid #3b82f6' : '1px solid transparent',
            color: activeSubTab === 'history' ? '#93c5fd' : 'var(--text-muted)',
            padding: '0.5rem 1.1rem',
            borderRadius: 'var(--radius-sm)',
            fontWeight: 700,
            fontSize: '0.875rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            transition: 'all 0.15s',
          }}
        >
          <History size={16} />
          Attendance History
        </button>
      </div>

      {activeSubTab === 'record' ? (
        <>
          {/* Class & Schedule Slot Selector Card */}
          <div className="glass-panel" style={{ borderLeft: '4px solid #10b981' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BookOpen size={18} color="#10b981" />
              Academic Class & Timetable Period Selector
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
              {/* Allocated Subject & Section */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.35rem' }}>
                  Course & Section Allocation:
                </label>
                <select
                  value={selectedAllocationId || ''}
                  onChange={(e) => setSelectedAllocationId(Number(e.target.value))}
                  disabled={allocations.length === 0}
                  style={{
                    width: '100%',
                    padding: '0.6rem 0.75rem',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-main)',
                    fontSize: '0.875rem',
                    fontWeight: 600,
                  }}
                >
                  {allocations.length === 0 && <option value="">No assigned classes available</option>}
                  {allocations.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.subject_code} - {a.subject_title} ({a.section_label})
                    </option>
                  ))}
                </select>
              </div>

              {/* Session Date (Future dates blocked by max) */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.35rem' }}>
                  Session Date (Max Today):
                </label>
                <input
                  type="date"
                  max={new Date().toISOString().split('T')[0]}
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.55rem 0.75rem',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-main)',
                    fontSize: '0.875rem',
                  }}
                />
              </div>

              {/* Session Type */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.35rem' }}>
                  Session Type:
                </label>
                <select
                  value={sessionType}
                  onChange={(e) => setSessionType(e.target.value as SessionType)}
                  style={{
                    width: '100%',
                    padding: '0.6rem 0.75rem',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-main)',
                    fontSize: '0.875rem',
                  }}
                >
                  <option value="REGULAR">Regular Lecture</option>
                  <option value="LAB">Laboratory Session</option>
                  <option value="TUTORIAL">Tutorial</option>
                  <option value="REMEDIAL">Remedial Class</option>
                </select>
              </div>
            </div>

            {allocations.length === 0 && (
              <div
                style={{
                  marginTop: '1rem',
                  padding: '0.85rem 1rem',
                  borderRadius: 'var(--radius-sm)',
                  background: 'rgba(245, 158, 11, 0.1)',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                  color: '#fde68a',
                  fontSize: '0.85rem',
                }}
              >
                No active class allocations were found for this account. Ask an administrator to assign a subject and section before recording attendance.
              </div>
            )}

            {/* Period Selector with Live Slot Availability Badges */}
            <div style={{ marginTop: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.45rem' }}>
                Select Period (Periods 1 - 7):
              </label>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {[1, 2, 3, 4, 5, 6, 7].map((p) => {
                  const isRecorded = rosterData?.recorded_periods.includes(p);
                  const isSelected = selectedPeriod === p;
                  return (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setSelectedPeriod(p)}
                      style={{
                        padding: '0.5rem 0.9rem',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '0.85rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '0.2rem',
                        transition: 'all 0.15s',
                        background: isSelected
                          ? 'rgba(16, 185, 129, 0.25)'
                          : isRecorded
                          ? 'rgba(239, 68, 68, 0.1)'
                          : 'var(--bg-card)',
                        border: isSelected
                          ? '1px solid #10b981'
                          : isRecorded
                          ? '1px solid rgba(239, 68, 68, 0.3)'
                          : '1px solid var(--border-subtle)',
                        color: isSelected
                          ? '#6ee7b7'
                          : isRecorded
                          ? '#fca5a5'
                          : 'var(--text-main)',
                      }}
                    >
                      <span>Period {p}</span>
                      <span
                        style={{
                          fontSize: '0.65rem',
                          fontWeight: 600,
                          color: isRecorded ? '#f87171' : '#34d399',
                        }}
                      >
                        {isRecorded ? 'Recorded' : 'Available'}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Topic Covered Field */}
            <div style={{ marginTop: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.35rem' }}>
                Topic / Syllabus Covered in Session:
              </label>
              <input
                type="text"
                placeholder="e.g. Unit 3: Relational Algebra, Selection & Projection Operators"
                value={topicCovered}
                onChange={(e) => setTopicCovered(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.55rem 0.75rem',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-main)',
                  fontSize: '0.875rem',
                }}
              />
            </div>

            {/* Warning if selected period is already recorded */}
            {isPeriodRecorded && (
              <div
                style={{
                  marginTop: '1rem',
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-sm)',
                  background: 'rgba(239, 68, 68, 0.12)',
                  border: '1px solid rgba(239, 68, 68, 0.35)',
                  color: '#fca5a5',
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <AlertCircle size={18} />
                <span>
                  <strong>Duplicate Slot Warning:</strong> Period {selectedPeriod} has already been recorded for this section & subject on {selectedDate}. To prevent duplicate records, select an available period or review previous records in Attendance History.
                </span>
              </div>
            )}
          </div>

          {/* Submission Success Alert */}
          {submissionSuccess && (
            <div
              className="glass-panel"
              style={{
                borderLeft: '4px solid #10b981',
                background: 'rgba(16, 185, 129, 0.08)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '1rem',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#6ee7b7', fontWeight: 700, fontSize: '1.05rem' }}>
                  <CheckCircle2 size={20} />
                  Attendance Session #{submissionSuccess.session.id} Committed Successfully!
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  Period {submissionSuccess.session.period_number} • {submissionSuccess.session.session_date} • {submissionSuccess.stats.present_count}/{submissionSuccess.stats.total_students} Present ({submissionSuccess.stats.attendance_percentage}%)
                </div>
              </div>
              <button
                onClick={() => {
                  setSubmissionSuccess(null);
                  setActiveSubTab('history');
                }}
                style={{
                  padding: '0.5rem 1rem',
                  background: 'rgba(16, 185, 129, 0.25)',
                  border: '1px solid #10b981',
                  color: '#6ee7b7',
                  borderRadius: 'var(--radius-sm)',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                View History
              </button>
            </div>
          )}

          {/* Submission Error Alert */}
          {submissionError && (
            <div
              className="glass-panel"
              style={{
                borderLeft: '4px solid #ef4444',
                background: 'rgba(239, 68, 68, 0.1)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                color: '#fca5a5',
                fontSize: '0.9rem',
              }}
            >
              <AlertTriangle size={20} />
              <div>
                <strong>Submission Error:</strong> {submissionError}
              </div>
            </div>
          )}

          {/* Deterministic Statistics & Live Counter Bar */}
          <div className="glass-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <h4 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>
                  Deterministic Session Attendance Calculation
                </h4>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.2rem' }}>
                  Formula: (Present + Late + On-Duty + Medical) / Total Students × 100
                </div>
              </div>

              {/* Attendance % Metric Badge */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '1.25rem', fontWeight: 800, color: attendancePercentage >= 75 ? '#34d399' : attendancePercentage >= 65 ? '#fbbf24' : '#f87171' }}>
                    {attendancePercentage.toFixed(2)}%
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
                    Statutory Floor: 75%
                  </div>
                </div>
              </div>
            </div>

            {/* Stat Counters Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.75rem' }}>
              <div style={{ background: 'var(--bg-card)', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-subtle)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Total Enrolled</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{totalStudents}</div>
              </div>
              <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.25)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: '#6ee7b7' }}>Present</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#34d399' }}>{presentCount}</div>
              </div>
              <div style={{ background: 'rgba(239, 68, 68, 0.1)', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.25)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: '#fca5a5' }}>Absent</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f87171' }}>{absentCount}</div>
              </div>
              <div style={{ background: 'rgba(245, 158, 11, 0.1)', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(245, 158, 11, 0.25)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: '#fde68a' }}>Late Arrival</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fbbf24' }}>{lateCount}</div>
              </div>
              <div style={{ background: 'rgba(59, 130, 246, 0.1)', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(59, 130, 246, 0.25)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: '#93c5fd' }}>On-Duty / Med</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#60a5fa' }}>{onDutyCount + medicalCount}</div>
              </div>
            </div>
          </div>

          {/* Quick Actions & Student Attendance Roster Grid */}
          <div className="glass-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
              <div>
                <h3 className="section-title" style={{ margin: 0 }}>
                  <Users size={18} color="#06b6d4" />
                  Student Attendance Roster ({students.length} Students)
                </h3>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Mark each student individually or use the quick bulk actions below.
                </div>
              </div>

              {/* Bulk Buttons & Review Submission */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={handleMarkAllPresent}
                  style={{
                    padding: '0.5rem 0.85rem',
                    background: 'rgba(16, 185, 129, 0.15)',
                    border: '1px solid rgba(16, 185, 129, 0.35)',
                    color: '#6ee7b7',
                    borderRadius: 'var(--radius-sm)',
                    fontWeight: 600,
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                  }}
                >
                  <Check size={14} /> Mark All Present
                </button>

                <button
                  type="button"
                  onClick={handleMarkAllAbsent}
                  style={{
                    padding: '0.5rem 0.85rem',
                    background: 'rgba(239, 68, 68, 0.12)',
                    border: '1px solid rgba(239, 68, 68, 0.35)',
                    color: '#fda4af',
                    borderRadius: 'var(--radius-sm)',
                    fontWeight: 600,
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                  }}
                >
                  <XCircle size={14} /> Mark All Absent
                </button>

                <button
                  type="button"
                  disabled={isPeriodRecorded || students.length === 0}
                  onClick={() => setIsReviewModalOpen(true)}
                  style={{
                    padding: '0.5rem 1.1rem',
                    background: isPeriodRecorded
                      ? 'rgba(100, 116, 139, 0.2)'
                      : 'linear-gradient(135deg, #10b981, #059669)',
                    border: 'none',
                    color: '#fff',
                    borderRadius: 'var(--radius-sm)',
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    cursor: isPeriodRecorded ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    boxShadow: isPeriodRecorded ? 'none' : '0 4px 12px rgba(16, 185, 129, 0.35)',
                  }}
                >
                  <FileCheck2 size={16} />
                  Review & Submit ({absentCount} Absent)
                </button>
              </div>
            </div>

            {/* Search Filter */}
            <div style={{ marginBottom: '1rem', position: 'relative' }}>
              <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
              <input
                type="text"
                placeholder="Search students by Roll Number or Name..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem 0.5rem 2.25rem',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-main)',
                  fontSize: '0.85rem',
                }}
              />
            </div>

            {/* Students Table */}
            {isLoadingRoster ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                Loading enrolled students roster...
              </div>
            ) : students.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                Select an assigned course and section to load its enrolled students.
              </div>
            ) : filteredStudents.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                No students found matching your criteria.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '120px' }}>Roll Number</th>
                      <th>Student Full Name</th>
                      <th style={{ width: '320px' }}>Mark Attendance Status</th>
                      <th style={{ width: '220px' }}>Optional Remarks</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredStudents.map((st) => (
                      <tr key={st.id}>
                        <td>
                          <code style={{ color: '#67e8f9', fontWeight: 700 }}>{st.roll_number}</code>
                        </td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{st.full_name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                            {st.registration_number} • {st.email}
                          </div>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '0.35rem' }}>
                            <button
                              type="button"
                              onClick={() => handleSetStudentStatus(st.id, 'PRESENT')}
                              style={{
                                padding: '0.35rem 0.65rem',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                cursor: 'pointer',
                                background: st.status === 'PRESENT' ? '#10b981' : 'rgba(16, 185, 129, 0.1)',
                                color: st.status === 'PRESENT' ? '#fff' : '#6ee7b7',
                                border: '1px solid rgba(16, 185, 129, 0.3)',
                                transition: 'all 0.1s',
                              }}
                            >
                              Present
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSetStudentStatus(st.id, 'ABSENT')}
                              style={{
                                padding: '0.35rem 0.65rem',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                cursor: 'pointer',
                                background: st.status === 'ABSENT' ? '#ef4444' : 'rgba(239, 68, 68, 0.1)',
                                color: st.status === 'ABSENT' ? '#fff' : '#fca5a5',
                                border: '1px solid rgba(239, 68, 68, 0.3)',
                                transition: 'all 0.1s',
                              }}
                            >
                              Absent
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSetStudentStatus(st.id, 'LATE')}
                              style={{
                                padding: '0.35rem 0.65rem',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                cursor: 'pointer',
                                background: st.status === 'LATE' ? '#f59e0b' : 'rgba(245, 158, 11, 0.1)',
                                color: st.status === 'LATE' ? '#fff' : '#fde68a',
                                border: '1px solid rgba(245, 158, 11, 0.3)',
                                transition: 'all 0.1s',
                              }}
                            >
                              Late
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSetStudentStatus(st.id, 'ON_DUTY')}
                              style={{
                                padding: '0.35rem 0.65rem',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                cursor: 'pointer',
                                background: st.status === 'ON_DUTY' ? '#3b82f6' : 'rgba(59, 130, 246, 0.1)',
                                color: st.status === 'ON_DUTY' ? '#fff' : '#93c5fd',
                                border: '1px solid rgba(59, 130, 246, 0.3)',
                                transition: 'all 0.1s',
                              }}
                            >
                              OD
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSetStudentStatus(st.id, 'MEDICAL_LEAVE')}
                              style={{
                                padding: '0.35rem 0.65rem',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                cursor: 'pointer',
                                background: st.status === 'MEDICAL_LEAVE' ? '#b45309' : 'rgba(245, 158, 11, 0.1)',
                                color: st.status === 'MEDICAL_LEAVE' ? '#fff' : '#fcd34d',
                                border: '1px solid rgba(245, 158, 11, 0.3)',
                                transition: 'all 0.1s',
                              }}
                            >
                              Med
                            </button>
                          </div>
                        </td>
                        <td>
                          <input
                            type="text"
                            placeholder="e.g. Arrived 15m late"
                            value={st.remarks}
                            onChange={(e) => handleSetStudentRemarks(st.id, e.target.value)}
                            style={{
                              width: '100%',
                              padding: '0.35rem 0.5rem',
                              background: 'var(--bg-card)',
                              border: '1px solid var(--border-subtle)',
                              borderRadius: '4px',
                              fontSize: '0.75rem',
                              color: 'var(--text-main)',
                            }}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : (
        /* Attendance History View */
        <div className="glass-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <div>
              <h3 className="section-title" style={{ margin: 0 }}>
                <History size={18} color="#3b82f6" />
                Conducted Attendance Sessions History
              </h3>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Historical log of sessions with deterministic statistics and audit trail.
              </div>
            </div>
            <button
              onClick={loadHistory}
              disabled={isLoadingHistory}
              style={{
                padding: '0.45rem 0.85rem',
                background: 'rgba(59, 130, 246, 0.15)',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                color: '#93c5fd',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
              }}
            >
              <RefreshCw size={14} /> Refresh
            </button>
          </div>

          {isLoadingHistory ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
              Loading attendance history...
            </div>
          ) : historySessions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
              No recorded sessions found for this section & subject.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Period</th>
                    <th>Course Code</th>
                    <th>Section</th>
                    <th>Topic Covered</th>
                    <th>Enrolled / Present</th>
                    <th>Attendance %</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {historySessions.map((s) => (
                    <tr key={s.id}>
                      <td><strong>{s.session_date}</strong></td>
                      <td>
                        <span className="badge-tag" style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#93c5fd' }}>
                          Period {s.period_number}
                        </span>
                      </td>
                      <td><code>{s.subject_code}</code></td>
                      <td>{s.section_label}</td>
                      <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {s.topic_covered || '—'}
                      </td>
                      <td>
                        {s.present_count} / {s.total_students}
                      </td>
                      <td>
                        <span
                          style={{
                            fontWeight: 700,
                            color: (s.attendance_percentage || 0) >= 75 ? '#34d399' : (s.attendance_percentage || 0) >= 65 ? '#fbbf24' : '#f87171',
                          }}
                        >
                          {s.attendance_percentage}%
                        </span>
                      </td>
                      <td>
                        <button
                          onClick={async () => {
                            try {
                              const detail = await api.getAttendanceSessionDetail(s.id);
                              setSelectedHistorySession(detail);
                            } catch (e: any) {
                              console.error('Failed to load session details:', e);
                            }
                          }}
                          style={{
                            padding: '0.35rem 0.75rem',
                            background: 'rgba(255, 255, 255, 0.08)',
                            border: '1px solid var(--border-subtle)',
                            color: 'var(--text-main)',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Pre-Submission Review Modal */}
      {isReviewModalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            className="glass-panel"
            style={{
              maxWidth: '600px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              border: '1px solid #10b981',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#6ee7b7' }}>
                <FileCheck2 size={20} />
                Attendance Submission Review
              </h3>
              <button
                onClick={() => setIsReviewModalOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            {/* Summary Details */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1rem', fontSize: '0.85rem' }}>
              <div>
                <span style={{ color: 'var(--text-dim)' }}>Course: </span>
                <strong>{currentAlloc?.subject_code} - {currentAlloc?.subject_title}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)' }}>Section: </span>
                <strong>{currentAlloc?.section_label}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)' }}>Date & Period: </span>
                <strong>{selectedDate} (Period {selectedPeriod})</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)' }}>Session Type: </span>
                <strong>{sessionType}</strong>
              </div>
              {topicCovered && (
                <div style={{ gridColumn: 'span 2' }}>
                  <span style={{ color: 'var(--text-dim)' }}>Topic Covered: </span>
                  <strong>{topicCovered}</strong>
                </div>
              )}
            </div>

            {/* Deterministic Stats Box */}
            <div style={{ background: 'var(--bg-card)', padding: '0.85rem', borderRadius: '8px', border: '1px solid var(--border-subtle)', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Attendance Summary</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 700, marginTop: '0.2rem' }}>
                    {presentCount} Present / {absentCount} Absent / {lateCount + onDutyCount + medicalCount} Other
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: attendancePercentage >= 75 ? '#34d399' : '#f87171' }}>
                    {attendancePercentage.toFixed(2)}%
                  </div>
                </div>
              </div>
            </div>

            {/* Explicit Absentees Verification Box */}
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fca5a5', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <AlertCircle size={16} />
                Absentees To Be Recorded ({absenteesList.length} Students):
              </div>
              {absenteesList.length === 0 ? (
                <div style={{ padding: '0.75rem', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '6px', color: '#6ee7b7', fontSize: '0.85rem' }}>
                  ✓ All {students.length} students are marked Present / Authorized.
                </div>
              ) : (
                <div style={{ maxHeight: '160px', overflowY: 'auto', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.08)' }}>
                  {absenteesList.map((a) => (
                    <div
                      key={a.id}
                      style={{
                        padding: '0.5rem 0.75rem',
                        borderBottom: '1px solid rgba(239, 68, 68, 0.15)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '0.8rem',
                      }}
                    >
                      <div>
                        <code style={{ color: '#fca5a5', fontWeight: 700 }}>{a.roll_number}</code>
                        <span style={{ marginLeft: '0.5rem', fontWeight: 600 }}>{a.full_name}</span>
                      </div>
                      {a.remarks && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                          ({a.remarks})
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Confirmation Buttons */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button
                type="button"
                onClick={() => setIsReviewModalOpen(false)}
                style={{
                  padding: '0.6rem 1.1rem',
                  background: 'transparent',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-main)',
                  borderRadius: 'var(--radius-sm)',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                Back to Edit
              </button>
              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleSubmitAttendance}
                style={{
                  padding: '0.6rem 1.35rem',
                  background: 'linear-gradient(135deg, #10b981, #059669)',
                  border: 'none',
                  color: '#fff',
                  borderRadius: 'var(--radius-sm)',
                  fontWeight: 700,
                  fontSize: '0.85rem',
                  cursor: isSubmitting ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  boxShadow: '0 4px 12px rgba(16, 185, 129, 0.35)',
                }}
              >
                <Send size={15} />
                {isSubmitting ? 'Committing...' : 'Confirm & Submit Attendance'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Session Detail Modal for History */}
      {selectedHistorySession && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            className="glass-panel"
            style={{
              maxWidth: '650px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              border: '1px solid var(--border-subtle)',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800, margin: 0 }}>
                Session #{selectedHistorySession.id} Breakdown
              </h3>
              <button
                onClick={() => setSelectedHistorySession(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', marginBottom: '1rem' }}>
              <div>Subject: <strong>{selectedHistorySession.subject_code} - {selectedHistorySession.subject_title}</strong></div>
              <div>Date & Period: <strong>{selectedHistorySession.session_date} (Period {selectedHistorySession.period_number})</strong></div>
              <div>Faculty: <strong>{selectedHistorySession.faculty_name}</strong></div>
              <div>Overall Attendance: <strong style={{ color: '#34d399' }}>{selectedHistorySession.attendance_percentage}%</strong></div>
            </div>

            <div style={{ maxHeight: '350px', overflowY: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Roll Number</th>
                    <th>Student Name</th>
                    <th>Status</th>
                    <th>Remarks</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedHistorySession.records?.map((r) => (
                    <tr key={r.id}>
                      <td><code style={{ color: '#67e8f9' }}>{r.student_roll}</code></td>
                      <td>{r.student_name}</td>
                      <td>
                        <span
                          className="badge-tag"
                          style={{
                            background: r.status === 'PRESENT' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                            color: r.status === 'PRESENT' ? '#6ee7b7' : '#fca5a5',
                          }}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td>{r.remarks || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
