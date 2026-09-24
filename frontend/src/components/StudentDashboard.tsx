import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { LoadingSpinner } from './LoadingSpinner';
import { EmptyState } from './EmptyState';
import { useToast } from './Toast';
import {
  GraduationCap, BookOpen, Clock, AlertTriangle, CheckCircle2,
  XCircle, Send, FileText, Calendar, TrendingUp, AlertCircle,
  ExternalLink, RefreshCw, History, ShieldAlert
} from 'lucide-react';

export const StudentDashboard: React.FC = () => {
  const { error: showError } = useToast();
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [corrections, setCorrections] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [profilePending, setProfilePending] = useState<boolean>(false);

  // Correction Submission Form Modal / Drawer
  const [selectedRecord, setSelectedRecord] = useState<any | null>(null);
  const [requestedStatus, setRequestedStatus] = useState<string>('MEDICAL_LEAVE');
  const [reason, setReason] = useState<string>('');
  const [documentUrl, setDocumentUrl] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [submitMessage, setSubmitMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Audit Log Timeline Modal
  const [auditTimeline, setAuditTimeline] = useState<any | null>(null);

  const fetchStudentDashboard = async () => {
    setLoading(true);
    setError(null);
    setProfilePending(false);
    try {
      const [dash, corr] = await Promise.all([
        api.getStudentDashboard(),
        api.getCorrections(),
      ]);
      setDashboardData(dash);
      setCorrections(corr.results || []);
    } catch (err: any) {
      console.error('Failed to load student dashboard:', err);
      if (err.status === 404 && String(err.message).toLowerCase().includes('student profile not found')) {
        setProfilePending(true);
      } else {
        setError(err.message || 'Failed to load student attendance data.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStudentDashboard();
  }, []);

  const handleOpenCorrection = (record: any) => {
    setSelectedRecord(record);
    setRequestedStatus(record.status === 'ABSENT' ? 'MEDICAL_LEAVE' : 'PRESENT');
    setReason('');
    setDocumentUrl('');
    setSubmitMessage(null);
  };

  const handleSubmitCorrection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRecord) return;
    if (!reason || reason.trim().length < 5) {
      setSubmitMessage({ type: 'error', text: 'Please provide a valid justification (minimum 5 characters).' });
      return;
    }

    setSubmitting(true);
    setSubmitMessage(null);
    try {
      await api.submitCorrection({
        record_id: selectedRecord.record_id,
        requested_status: requestedStatus,
        reason: reason.trim(),
        document_url: documentUrl.trim(),
      });
      setSubmitMessage({ type: 'success', text: 'Correction request submitted successfully! Awaiting faculty review.' });
      setTimeout(() => {
        setSelectedRecord(null);
        fetchStudentDashboard();
      }, 1500);
    } catch (err: any) {
      setSubmitMessage({ type: 'error', text: err.message || 'Failed to submit correction request.' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleViewAuditTrail = async (recordId: number) => {
    try {
      const trail = await api.getRecordAuditLogs(recordId);
      setAuditTimeline(trail);
    } catch (err: any) {
      showError('Could not load audit history', err.message || 'Please try again.');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Top Banner */}
      <div className="glass-panel" style={{ borderLeft: '4px solid #22d3ee' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div className="header-badge" style={{ marginBottom: '0.4rem', background: 'rgba(34, 211, 238, 0.15)', color: '#a5f3fc', borderColor: 'rgba(34, 211, 238, 0.3)' }}>
              <GraduationCap size={14} />
              Student Academic Portal
            </div>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 800 }}>
              {profilePending
                ? 'Student profile setup'
                : `Attendance & Compliance Record: ${dashboardData?.student?.full_name || 'Student'} (${dashboardData?.student?.roll_number || ''})`}
            </h2>
            {dashboardData?.student && (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
                Enrolled in {dashboardData.student.department_name} • {dashboardData.student.section_label} • Semester {dashboardData.student.semester} • Mentor: {dashboardData.student.mentor_name}
              </p>
            )}
          </div>

          <button
            onClick={fetchStudentDashboard}
            style={{
              background: 'rgba(34, 211, 238, 0.15)',
              border: '1px solid rgba(34, 211, 238, 0.4)',
              color: '#a5f3fc',
              padding: '0.6rem 1rem',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="glass-panel">
          <LoadingSpinner message="Calculating your attendance percentage…" />
        </div>
      ) : profilePending ? (
        <div className="glass-panel" style={{ borderLeft: '4px solid #f59e0b', color: '#fcd34d' }}>
          <EmptyState
            variant="no-data"
            title="Academic profile pending"
            message="Your account is active, but an administrator has not assigned your student profile, section, or courses yet. Attendance will appear here after your academic records are assigned."
            action={(
              <button
                onClick={fetchStudentDashboard}
                style={{
                  background: 'rgba(245, 158, 11, 0.15)',
                  border: '1px solid rgba(245, 158, 11, 0.4)',
                  color: '#fcd34d',
                  padding: '0.6rem 1rem',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  fontWeight: 600,
                }}
              >
                Check again
              </button>
            )}
          />
        </div>
      ) : error ? (
        <div className="glass-panel" style={{ borderLeft: '4px solid #f43f5e', color: '#fda4af' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertTriangle size={20} />
            <span style={{ fontWeight: 700 }}>Error loading dashboard:</span>
            <span>{error}</span>
          </div>
        </div>
      ) : dashboardData ? (
        <>
          {/* Active Low Attendance Warnings Alert Banner */}
          {dashboardData.low_attendance_warnings?.has_warnings && (
            <div className="glass-panel" style={{
              background: 'rgba(244, 63, 94, 0.08)',
              border: '1px solid rgba(244, 63, 94, 0.35)',
              borderLeft: '5px solid #f43f5e',
              padding: '1.25rem 1.5rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#fda4af', fontWeight: 800, fontSize: '1.1rem' }}>
                <AlertTriangle size={22} style={{ color: '#f43f5e' }} />
                <span>Statutory Attendance Shortage Warning Notice</span>
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.4rem' }}>
                Your attendance in <strong>{dashboardData.low_attendance_warnings.warnings_count}</strong> course(s) has fallen strictly below the mandatory {dashboardData.threshold_used}% institutional threshold.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1rem' }}>
                {dashboardData.low_attendance_warnings.warnings.map((w: any, idx: number) => (
                  <div key={idx} style={{
                    background: 'rgba(15, 23, 42, 0.6)',
                    padding: '0.75rem 1rem',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid rgba(244, 63, 94, 0.25)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '0.5rem'
                  }}>
                    <div>
                      <span style={{ fontWeight: 800, color: '#fff' }}>{w.subject_code} - {w.subject_title}</span>
                      <div style={{ fontSize: '0.8rem', color: '#fda4af', marginTop: '0.2rem' }}>
                        Current: <strong>{w.current_percentage}%</strong> (Shortfall Deficit: -{w.deficit_percentage}%)
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{
                        padding: '0.25rem 0.6rem',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        background: 'rgba(244, 63, 94, 0.2)',
                        color: '#fca5a5'
                      }}>
                        Must attend next {w.classes_needed_to_recover} consecutive classes
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Key Overall Statistics Row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem' }}>
            <div className="glass-panel" style={{
              borderLeft: dashboardData.overall_attendance.is_low_attendance ? '4px solid #f43f5e' : '4px solid #10b981'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Overall Attendance</span>
                <TrendingUp size={18} style={{ color: dashboardData.overall_attendance.is_low_attendance ? '#f87171' : '#34d399' }} />
              </div>
              <div style={{
                fontSize: '2.4rem',
                fontWeight: 800,
                marginTop: '0.4rem',
                color: dashboardData.overall_attendance.is_low_attendance ? '#f87171' : '#34d399'
              }}>
                {dashboardData.overall_attendance.overall_percentage}%
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                Status: <strong style={{ color: dashboardData.overall_attendance.is_low_attendance ? '#fda4af' : '#6ee7b7' }}>
                  {dashboardData.overall_attendance.overall_status}
                </strong>
              </div>
            </div>

            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Conducted Sessions</span>
                <Calendar size={18} style={{ color: '#60a5fa' }} />
              </div>
              <div style={{ fontSize: '2.4rem', fontWeight: 800, marginTop: '0.4rem' }}>
                {dashboardData.overall_attendance.total_conducted}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#93c5fd', marginTop: '0.2rem' }}>
                Total academic periods
              </div>
            </div>

            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Classes Attended</span>
                <CheckCircle2 size={18} style={{ color: '#34d399' }} />
              </div>
              <div style={{ fontSize: '2.4rem', fontWeight: 800, marginTop: '0.4rem', color: '#34d399' }}>
                {dashboardData.overall_attendance.total_attended}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#6ee7b7', marginTop: '0.2rem' }}>
                Present + Late + Authorized
              </div>
            </div>

            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Classes Missed</span>
                <XCircle size={18} style={{ color: '#f87171' }} />
              </div>
              <div style={{ fontSize: '2.4rem', fontWeight: 800, marginTop: '0.4rem', color: '#f87171' }}>
                {dashboardData.overall_attendance.total_missed}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#fda4af', marginTop: '0.2rem' }}>
                Unexcused absences
              </div>
            </div>

            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Target Recovery Margin</span>
                <Clock size={18} style={{ color: '#a78bfa' }} />
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '0.4rem' }}>
                {dashboardData.overall_attendance.is_low_attendance ? (
                  <span style={{ color: '#f87171' }}>+{dashboardData.overall_attendance.classes_needed_for_target} needed</span>
                ) : (
                  <span style={{ color: '#34d399' }}>{dashboardData.overall_attendance.classes_can_miss_for_target} can miss</span>
                )}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                To maintain {dashboardData.threshold_used}% eligibility
              </div>
            </div>
          </div>

          {/* Subject-Wise Attendance Table */}
          <div className="glass-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <BookOpen size={20} style={{ color: '#22d3ee' }} />
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Subject-Wise Attendance Breakdown</h3>
              </div>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Minimum Statutory Requirement: {dashboardData.threshold_used}%
              </span>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '0.75rem' }}>Subject Code</th>
                    <th style={{ padding: '0.75rem' }}>Subject Title</th>
                    <th style={{ padding: '0.75rem' }}>Credits</th>
                    <th style={{ padding: '0.75rem' }}>Conducted / Attended</th>
                    <th style={{ padding: '0.75rem' }}>Attendance %</th>
                    <th style={{ padding: '0.75rem' }}>Recovery Target</th>
                    <th style={{ padding: '0.75rem' }}>Statutory Status</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboardData.subject_wise_attendance?.map((s: any, idx: number) => {
                    const isLow = s.is_low_attendance;
                    const isCritical = s.status === 'CRITICAL' || s.attendance_percentage < 65;
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.75rem', fontWeight: 800, color: '#a5f3fc' }}>{s.subject_code}</td>
                        <td style={{ padding: '0.75rem', fontWeight: 600 }}>{s.subject_title}</td>
                        <td style={{ padding: '0.75rem', color: 'var(--text-muted)' }}>{s.credits} Credits</td>
                        <td style={{ padding: '0.75rem' }}>{s.classes_attended} / {s.classes_conducted}</td>
                        <td style={{ padding: '0.75rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                            <span style={{ fontWeight: 800, color: isLow ? '#f43f5e' : '#34d399', width: '45px' }}>
                              {s.attendance_percentage}%
                            </span>
                            <div style={{ width: '80px', height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                              <div style={{
                                width: `${Math.min(100, s.attendance_percentage)}%`,
                                height: '100%',
                                background: isLow ? '#f43f5e' : '#10b981',
                                borderRadius: '3px'
                              }} />
                            </div>
                          </div>
                        </td>
                        <td style={{ padding: '0.75rem' }}>
                          {isLow ? (
                            <span style={{ color: '#fda4af', fontWeight: 700 }}>
                              +{s.classes_needed_for_75} consecutive
                            </span>
                          ) : (
                            <span style={{ color: '#6ee7b7', fontSize: '0.8rem' }}>
                              {s.classes_can_miss_for_75} safe margin
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '0.75rem' }}>
                          <span style={{
                            padding: '0.2rem 0.55rem',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            background: isCritical ? 'rgba(244, 63, 94, 0.15)' : isLow ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                            color: isCritical ? '#fda4af' : isLow ? '#fde68a' : '#6ee7b7',
                            border: `1px solid ${isCritical ? 'rgba(244, 63, 94, 0.3)' : isLow ? 'rgba(245, 158, 11, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`
                          }}>
                            {s.status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Attendance History & Dispute Logging */}
          <div className="glass-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <History size={20} style={{ color: '#60a5fa' }} />
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Recent Attendance History & Corrections</h3>
              </div>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Click "Dispute" on any record to initiate a formal correction workflow
              </span>
            </div>

            {dashboardData.attendance_history && dashboardData.attendance_history.length > 0 ? (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '0.75rem' }}>Date & Period</th>
                      <th style={{ padding: '0.75rem' }}>Subject</th>
                      <th style={{ padding: '0.75rem' }}>Teacher</th>
                      <th style={{ padding: '0.75rem' }}>Recorded Status</th>
                      <th style={{ padding: '0.75rem' }}>Remarks</th>
                      <th style={{ padding: '0.75rem' }}>Audit & Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboardData.attendance_history.map((h: any, idx: number) => {
                      const isPresent = h.status === 'PRESENT';
                      const isAbsent = h.status === 'ABSENT';
                      return (
                        <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td style={{ padding: '0.75rem', fontWeight: 600 }}>
                            {h.session_date} <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>(Period {h.period_number})</span>
                          </td>
                          <td style={{ padding: '0.75rem' }}>
                            <div style={{ fontWeight: 700, color: '#a5f3fc' }}>{h.subject_code}</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{h.subject_title}</div>
                          </td>
                          <td style={{ padding: '0.75rem', color: 'var(--text-muted)' }}>{h.faculty_name}</td>
                          <td style={{ padding: '0.75rem' }}>
                            <span style={{
                              padding: '0.2rem 0.55rem',
                              borderRadius: '4px',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              background: isPresent ? 'rgba(16, 185, 129, 0.15)' : isAbsent ? 'rgba(244, 63, 94, 0.15)' : 'rgba(59, 130, 246, 0.15)',
                              color: isPresent ? '#6ee7b7' : isAbsent ? '#fda4af' : '#93c5fd',
                              border: `1px solid ${isPresent ? 'rgba(16, 185, 129, 0.3)' : isAbsent ? 'rgba(244, 63, 94, 0.3)' : 'rgba(59, 130, 246, 0.3)'}`
                            }}>
                              {h.status_display || h.status}
                            </span>
                          </td>
                          <td style={{ padding: '0.75rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                            {h.remarks || '—'}
                          </td>
                          <td style={{ padding: '0.75rem' }}>
                            <div style={{ display: 'flex', gap: '0.4rem' }}>
                              <button
                                onClick={() => handleOpenCorrection(h)}
                                style={{
                                  background: 'rgba(245, 158, 11, 0.15)',
                                  border: '1px solid rgba(245, 158, 11, 0.35)',
                                  color: '#fde68a',
                                  padding: '0.3rem 0.6rem',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '0.75rem',
                                  fontWeight: 600
                                }}
                              >
                                Dispute
                              </button>
                              <button
                                onClick={() => handleViewAuditTrail(h.record_id)}
                                style={{
                                  background: 'rgba(255, 255, 255, 0.05)',
                                  border: '1px solid var(--border-color)',
                                  color: 'var(--text-muted)',
                                  padding: '0.3rem 0.6rem',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '0.75rem'
                                }}
                              >
                                Timeline
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No attendance sessions recorded for your section yet.
              </div>
            )}
          </div>

          {/* Submitted Correction Requests Status */}
          {corrections && corrections.length > 0 && (
            <div className="glass-panel">
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1rem' }}>
                Your Submitted Correction Disputes
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {corrections.map((c: any) => (
                  <div key={c.id} style={{
                    background: 'rgba(15, 23, 42, 0.4)',
                    padding: '0.85rem 1rem',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-color)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '0.5rem'
                  }}>
                    <div>
                      <div style={{ fontWeight: 700 }}>
                        Correction #{c.id} • {c.subject_code} ({c.session_date})
                      </div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                        Requested: <strong style={{ color: '#6ee7b7' }}>{c.requested_status}</strong> (Original: {c.old_status}) • Reason: {c.reason}
                      </div>
                      {c.review_notes && (
                        <div style={{ fontSize: '0.8rem', color: '#93c5fd', marginTop: '0.2rem' }}>
                          Staff Review Notes: {c.review_notes}
                        </div>
                      )}
                    </div>
                    <span style={{
                      padding: '0.25rem 0.6rem',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      background: c.status === 'APPROVED' ? 'rgba(16, 185, 129, 0.15)' : c.status === 'REJECTED' ? 'rgba(244, 63, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                      color: c.status === 'APPROVED' ? '#6ee7b7' : c.status === 'REJECTED' ? '#fda4af' : '#fde68a',
                      border: `1px solid ${c.status === 'APPROVED' ? 'rgba(16, 185, 129, 0.3)' : c.status === 'REJECTED' ? 'rgba(244, 63, 94, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`
                    }}>
                      {c.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : null}

      {/* Submit Correction Modal */}
      {selectedRecord && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '1rem'
        }}>
          <div className="glass-panel" style={{ width: '100%', maxWidth: '520px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.15)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Initiate Attendance Dispute</h3>
              <button onClick={() => setSelectedRecord(null)} style={{ background: 'none', border: 'none', color: '#fff', fontSize: '1.2rem', cursor: 'pointer' }}>×</button>
            </div>

            <form onSubmit={handleSubmitCorrection} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.2rem' }}>Subject & Session:</label>
                <div style={{ fontWeight: 700 }}>{selectedRecord.subject_code} - {selectedRecord.subject_title} ({selectedRecord.session_date} Period {selectedRecord.period_number})</div>
                <div style={{ fontSize: '0.8rem', color: '#fda4af', marginTop: '0.2rem' }}>Currently marked as: <strong>{selectedRecord.status}</strong></div>
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.2rem' }}>Requested Correction Status:</label>
                <select
                  value={requestedStatus}
                  onChange={(e) => setRequestedStatus(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid var(--border-color)',
                    color: '#fff',
                    padding: '0.6rem 0.8rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.85rem'
                  }}
                >
                  <option value="PRESENT">Present (Marked absent by mistake)</option>
                  <option value="MEDICAL_LEAVE">Medical Leave (Hospitalization / Illness)</option>
                  <option value="ON_DUTY">On Duty (Event / Competition / Hackathon)</option>
                  <option value="LATE">Late (Admitted with permission)</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.2rem' }}>Detailed Justification (Required):</label>
                <textarea
                  rows={3}
                  required
                  placeholder="Explain justification (e.g. Dengue fever hospitalization at City General Hospital)..."
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid var(--border-color)',
                    color: '#fff',
                    padding: '0.6rem 0.8rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.85rem',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.2rem' }}>Supporting Document URL (Optional):</label>
                <input
                  type="url"
                  placeholder="https://edumerge.ac.in/docs/medical_slip.pdf"
                  value={documentUrl}
                  onChange={(e) => setDocumentUrl(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid var(--border-color)',
                    color: '#fff',
                    padding: '0.6rem 0.8rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.85rem',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              {submitMessage && (
                <div style={{
                  padding: '0.6rem 0.8rem',
                  borderRadius: '4px',
                  fontSize: '0.85rem',
                  background: submitMessage.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
                  color: submitMessage.type === 'success' ? '#6ee7b7' : '#fda4af',
                  border: `1px solid ${submitMessage.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`
                }}>
                  {submitMessage.text}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setSelectedRecord(null)}
                  style={{
                    background: 'transparent',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-muted)',
                    padding: '0.5rem 1rem',
                    borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{
                    background: 'linear-gradient(135deg, #0891b2, #0e7490)',
                    border: 'none',
                    color: '#fff',
                    padding: '0.5rem 1.25rem',
                    borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer',
                    fontWeight: 700
                  }}
                >
                  {submitting ? 'Submitting...' : 'Submit Dispute'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Audit Timeline Modal */}
      {auditTimeline && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '1rem'
        }}>
          <div className="glass-panel" style={{ width: '100%', maxWidth: '580px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.15)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <History size={18} style={{ color: '#60a5fa' }} />
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Immutable Record Audit Timeline</h3>
              </div>
              <button onClick={() => setAuditTimeline(null)} style={{ background: 'none', border: 'none', color: '#fff', fontSize: '1.2rem', cursor: 'pointer' }}>×</button>
            </div>

            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              Record ID: #{auditTimeline.record_id} • Subject: {auditTimeline.subject_code} ({auditTimeline.session_date}) • Current Status: <strong>{auditTimeline.current_status}</strong>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '350px', overflowY: 'auto' }}>
              {auditTimeline.audit_trail && auditTimeline.audit_trail.length > 0 ? (
                auditTimeline.audit_trail.map((entry: any, idx: number) => (
                  <div key={idx} style={{
                    background: 'rgba(255,255,255,0.03)',
                    borderLeft: '3px solid #60a5fa',
                    padding: '0.75rem 1rem',
                    borderRadius: '4px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span style={{ fontWeight: 700, color: '#93c5fd' }}>{entry.action_display || entry.action}</span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{entry.timestamp?.slice(0, 19).replace('T', ' ')}</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', marginTop: '0.2rem' }}>
                      Status Transition: <strong style={{ color: '#fda4af' }}>{entry.previous_status || 'Initial'}</strong> &rarr; <strong style={{ color: '#6ee7b7' }}>{entry.new_status}</strong>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      Changed by: {entry.changed_by_name || 'System'} • Reason: {entry.reason || 'N/A'}
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No historical audit entries for this record.
                </div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
              <button
                onClick={() => setAuditTimeline(null)}
                style={{
                  background: 'rgba(255,255,255,0.1)',
                  border: '1px solid var(--border-color)',
                  color: '#fff',
                  padding: '0.4rem 1rem',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer'
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
