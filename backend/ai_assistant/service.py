"""
AI Attendance Assistant Service.

Guarantees:
1. Strictly READ-ONLY. Never modifies database records or session logs.
2. Zero arbitrary SQL: all data access is mediated through deterministic Python tools.
3. The LLM never calculates percentages itself; all percentages and recovery targets are
   pre-computed by the backend.
4. If data is unavailable, responses state that clearly.
5. Role-based scoping prevents unauthorized cross-student data leakage.
"""

import os
import re
from typing import Dict, Any, Optional
from datetime import datetime

from django.conf import settings
from . import tools


class AIAttendanceAssistantService:
    """
    Central service for answering natural language attendance queries using
    deterministic backend tools and read-only AI explanations.
    """

    AVAILABLE_TOOLS = {
        'get_student_attendance': {
            'description': "Retrieves overall and subject-wise attendance calculations for a student by roll number or name.",
            'parameters': {'student_identifier': 'str (roll number or name)', 'threshold': 'float (optional)'}
        },
        'get_low_attendance_students': {
            'description': "Returns students falling strictly below a specified percentage threshold (default 75%).",
            'parameters': {'threshold': 'float (e.g. 75, 70)', 'department_code': 'str (optional)'}
        },
        'get_subject_attendance': {
            'description': "Computes average attendance per course and identifies subjects with highest and lowest attendance.",
            'parameters': {'subject_code': 'str (optional)', 'department_code': 'str (optional)'}
        },
        'get_department_attendance': {
            'description': "Ranks university departments by aggregated attendance percentage and identifies lowest/highest departments.",
            'parameters': {}
        },
        'get_attendance_history': {
            'description': "Retrieves chronological attendance logs for a student or course over a given window in days.",
            'parameters': {'student_identifier': 'str (optional)', 'subject_code': 'str (optional)', 'days': 'int (optional)'}
        },
        'get_attendance_statistics': {
            'description': "Analyzes attendance trends and percentage changes over time (week, month, semester).",
            'parameters': {'time_frame': 'str (week, month, semester)', 'department_code': 'str (optional)'}
        }
    }

    @classmethod
    def list_available_tools(cls) -> Dict[str, Any]:
        """Returns the catalog of registered read-only backend tools."""
        return cls.AVAILABLE_TOOLS

    @classmethod
    def process_query(cls, user, query_text: str) -> Dict[str, Any]:
        """
        Executes a natural language query on behalf of the authenticated user.
        
        Steps:
        1. Check role-based security permissions.
        2. Intelligently determine which deterministic tool to call and extract arguments.
        3. Execute the read-only tool function directly against the database.
        4. Generate a comprehensive explanation (using Gemini LLM if API key is configured,
           or deterministic NLG explainer).
        5. Return the explanation along with the structured tool results.
        """
        query = str(query_text).strip()
        if not query:
            return {
                'success': False,
                'error': "Query cannot be empty. Please ask an attendance-related question."
            }

        # 1. Intent recognition & parameter extraction
        intent, params = cls._classify_intent_and_extract_parameters(query, user)

        # 2. Enforce Role-Based Scoping
        if user.role == 'STUDENT':
            # Students may only query their own attendance or general subject rankings
            if intent == 'get_low_attendance_students':
                return {
                    'success': True,
                    'query': query,
                    'tool_called': intent,
                    'tool_parameters': params,
                    'tool_result': {'status': 'forbidden', 'message': "Privacy protection: Students cannot view institutional low attendance lists."},
                    'answer': (
                        "For student privacy protection, you can only view your own attendance record. "
                        "Please check your personal dashboard or ask 'Show my attendance'."
                    ),
                    'execution_source': 'security_guard'
                }
            elif intent == 'get_student_attendance':
                target = params.get('student_identifier', '').lower()
                user_username = user.username.lower()
                user_first = user.first_name.lower() if user.first_name else ''
                # Allow if target matches current user or if user asks "my attendance"
                if target in ['my', 'me', 'mine', user_username, user_first]:
                    params['student_identifier'] = user.username
                elif target != user_username and target != user_first:
                    # Block querying another student
                    return {
                        'success': True,
                        'query': query,
                        'tool_called': intent,
                        'tool_parameters': params,
                        'tool_result': {'status': 'forbidden', 'message': "Privacy protection: You cannot view another student's record."},
                        'answer': "You do not have permission to view other students' attendance details. You can only view your own record.",
                        'execution_source': 'security_guard'
                    }

        # 3. Execute the corresponding deterministic tool
        tool_result = cls._dispatch_tool(intent, params)

        # 4. Generate natural language explanation
        explanation = cls._generate_explanation(query, intent, params, tool_result)

        return {
            'success': True,
            'query': query,
            'tool_called': intent,
            'tool_parameters': params,
            'tool_result': tool_result,
            'answer': explanation['text'],
            'execution_source': explanation['source'],
            'timestamp': datetime.now().isoformat()
        }

    @classmethod
    def _classify_intent_and_extract_parameters(cls, query: str, user) -> tuple:
        """
        Parses user query to identify which deterministic backend tool to call
        and extracts arguments (names, roll numbers, percentage thresholds, time frames).
        """
        q = query.lower()

        # Check for student attendance query ("Show Rahul's attendance", "Show my attendance", "attendance of 24CSE001")
        if any(term in q for term in ['show', 'get', 'what is', 'how is', 'check']) and 'attendance' in q and not any(k in q for k in ['lowest', 'below', 'changed', 'month', 'department', 'subject', 'trend']):
            # Extract target
            # E.g. "show rahul's attendance" -> extract "rahul"
            m = re.search(r"(?:show|get|what is|check)\s+([a-zA-Z0-9_\-]+)(?:'s)?\s+attendance", q)
            if m:
                target = m.group(1).strip()
                if target in ['my', 'me', 'mine']:
                    target = user.username
                return 'get_student_attendance', {'student_identifier': target}
            
            # E.g. "attendance of rahul" or "attendance for rahul"
            m2 = re.search(r"attendance\s+(?:of|for)\s+([a-zA-Z0-9_\-]+)", q)
            if m2:
                target = m2.group(1).strip()
                if target in ['my', 'me', 'mine']:
                    target = user.username
                return 'get_student_attendance', {'student_identifier': target}

            # If user asks simply "my attendance"
            if 'my attendance' in q:
                return 'get_student_attendance', {'student_identifier': user.username}

        # Check for low attendance students query ("Which students are below 75%?", "students below 70%")
        if 'below' in q or 'shortage' in q or 'low attendance' in q or 'at risk' in q:
            # Extract percentage number if specified (e.g. 70%, 75%, 80%)
            m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", q)
            threshold = 75.0
            if m_pct:
                try:
                    threshold = float(m_pct.group(1))
                except ValueError:
                    threshold = 75.0
            else:
                m_num = re.search(r"below\s+(\d+(?:\.\d+)?)", q)
                if m_num:
                    try:
                        threshold = float(m_num.group(1))
                    except ValueError:
                        threshold = 75.0

            # Extract optional department
            dept = cls._extract_department(q)
            return 'get_low_attendance_students', {'threshold': threshold, 'department_code': dept}

        # Check for lowest subject attendance query ("Which subjects have the lowest attendance?")
        if ('subject' in q or 'course' in q) and ('lowest' in q or 'poor' in q or 'bottom' in q or 'worst' in q):
            dept = cls._extract_department(q)
            return 'get_subject_attendance', {'department_code': dept}

        # Check for specific subject attendance ("Show CS401 attendance", "How is CS401 doing?")
        m_subj = re.search(r"\b([A-Za-z]{2,4}\d{3,4})\b", query)
        if m_subj and not any(k in q for k in ['student', 'department', 'month', 'changed']):
            subj_code = m_subj.group(1).upper()
            return 'get_subject_attendance', {'subject_code': subj_code}

        # Check for department attendance query ("Which department has the lowest attendance?", "Show department attendance")
        if 'department' in q:
            return 'get_department_attendance', {}

        # Check for attendance history query ("attendance history", "history of sessions")
        if 'history' in q or 'past sessions' in q or 'recent classes' in q:
            days = 30
            m_days = re.search(r"(\d+)\s*days", q)
            if m_days:
                try:
                    days = int(m_days.group(1))
                except ValueError:
                    days = 30
            # Check for student filter
            target = None
            if user.role == 'STUDENT':
                target = user.username
            return 'get_attendance_history', {'student_identifier': target, 'days': days}

        # Check for trends / statistics query ("How has attendance changed this month?", "monthly attendance trend")
        if any(w in q for w in ['changed', 'month', 'monthly', 'trend', 'statistics', 'stats', 'week', 'weekly', 'rate']):
            time_frame = 'month'
            if 'week' in q:
                time_frame = 'week'
            elif 'semester' in q:
                time_frame = 'semester'
            dept = cls._extract_department(q)
            return 'get_attendance_statistics', {'time_frame': time_frame, 'department_code': dept}

        # Fallback: Check if query contains any student name/roll number
        words = [w for w in re.findall(r'\b[A-Za-z0-9_\-]+\b', query) if len(w) >= 3 and w.lower() not in ['what', 'show', 'tell', 'attendance', 'check', 'view', 'list', 'please']]
        if words:
            # Try student attendance with first significant word
            return 'get_student_attendance', {'student_identifier': words[0]}

        # Default fallback: general statistics
        return 'get_attendance_statistics', {'time_frame': 'month'}

    @classmethod
    def _extract_department(cls, q: str) -> Optional[str]:
        """Extracts known department codes from text query."""
        known_depts = ['CSE', 'ECE', 'MECH', 'CHEM', 'IT', 'CIVIL', 'EEE']
        for d in known_depts:
            if re.search(r'\b' + d.lower() + r'\b', q):
                return d
        return None

    @classmethod
    def _dispatch_tool(cls, intent: str, params: dict) -> Dict[str, Any]:
        """Dispatches the intent to the designated read-only tool function."""
        if intent == 'get_student_attendance':
            return tools.get_student_attendance(
                student_identifier=params.get('student_identifier', ''),
                threshold=params.get('threshold')
            )
        elif intent == 'get_low_attendance_students':
            return tools.get_low_attendance_students(
                threshold=params.get('threshold', 75.0),
                department_code=params.get('department_code')
            )
        elif intent == 'get_subject_attendance':
            return tools.get_subject_attendance(
                subject_code=params.get('subject_code'),
                department_code=params.get('department_code')
            )
        elif intent == 'get_department_attendance':
            return tools.get_department_attendance()
        elif intent == 'get_attendance_history':
            return tools.get_attendance_history(
                student_identifier=params.get('student_identifier'),
                subject_code=params.get('subject_code'),
                days=params.get('days', 30)
            )
        elif intent == 'get_attendance_statistics':
            return tools.get_attendance_statistics(
                time_frame=params.get('time_frame', 'month'),
                department_code=params.get('department_code')
            )
        else:
            return {'status': 'error', 'message': f"Unknown tool intent: {intent}"}

    @classmethod
    def _generate_explanation(cls, query: str, intent: str, params: dict, tool_result: dict) -> Dict[str, str]:
        """
        Produces a rich, human-friendly natural language explanation of the structured tool result.
        Attempts to use Google Gemini if GEMINI_API_KEY / GOOGLE_API_KEY is available,
        otherwise uses our deterministic NLG explainer.
        """
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                system_instruction = (
                    "You are the Edumerge Smart Attendance Read-Only AI Assistant. "
                    "You NEVER calculate attendance percentages yourself; all numbers are calculated by the deterministic backend. "
                    "Explain the structured JSON results clearly and concisely to answer the user's question. "
                    "If data is unavailable, clearly state so. Never output SQL code."
                )
                prompt = (
                    f"{system_instruction}\n\n"
                    f"User Query: {query}\n"
                    f"Tool Executed: {intent}\n"
                    f"Parameters: {params}\n"
                    f"Tool Result JSON:\n{tool_result}\n\n"
                    f"Provide a helpful, precise explanation directly answering the question based only on this data."
                )
                resp = model.generate_content(prompt)
                if resp and resp.text:
                    return {'text': resp.text.strip(), 'source': 'gemini_llm'}
            except Exception as e:
                # If Gemini fails or times out, smoothly fallback to deterministic explainer
                pass

        # Deterministic Natural Language Generator (NLG) Explainer
        nlg_text = cls._explain_deterministically(intent, params, tool_result)
        return {'text': nlg_text, 'source': 'deterministic_engine'}

    @classmethod
    def _explain_deterministically(cls, intent: str, params: dict, res: dict) -> str:
        """
        Deterministic explainer that produces clear, accurate explanations
        from structured tool outputs without calculating any numbers itself.
        """
        if res.get('status') == 'not_found':
            return res.get('message', "The requested academic record was not found.")

        if res.get('status') == 'ambiguous':
            candidates = res.get('candidates', [])
            cand_str = ", ".join([f"{c['name']} ({c['roll_number']})" for c in candidates])
            return f"Multiple students match that name: {cand_str}. Please specify the exact roll number."

        if intent == 'get_student_attendance':
            st = res.get('student', {})
            att = res.get('overall_attendance', {})
            pct = att.get('overall_percentage', 0.0)
            cond = att.get('total_conducted', 0)
            attended = att.get('total_attended', 0)
            missed = att.get('total_missed', 0)
            thresh = res.get('threshold_used', 75.0)
            is_low = att.get('is_low_attendance', False)
            needed = att.get('classes_needed_for_target', 0)
            can_miss = att.get('classes_can_miss_for_target', 0)

            if cond == 0:
                return (
                    f"**{st.get('full_name')}** ({st.get('roll_number')}, {st.get('department')}) currently has "
                    f"**0 classes conducted** across all enrolled subjects. Attendance percentage is 0.0% until classes commence."
                )

            status_str = "Below Statutory Threshold" if is_low else "Satisfactory"
            lines = [
                f"**{st.get('full_name')}** ({st.get('roll_number')}) — Department of {st.get('department')}, Section {st.get('section')}:",
                f"- **Overall Attendance:** **{pct}%** ({attended}/{cond} classes attended, {missed} missed).",
                f"- **Compliance Status:** **{status_str}** (Mandatory Threshold: {thresh}%).",
            ]
            if is_low:
                lines.append(f"- **Recovery Requirement:** Must attend the next **{needed} consecutive classes** without absence to reach {thresh}%.")
            else:
                lines.append(f"- **Buffer Margin:** Can afford to miss up to **{can_miss} classes** while maintaining $\\ge${thresh}%.")

            # Subject breakdown
            subjs = res.get('subjects', [])
            if subjs:
                lines.append("\n**Subject-Wise Breakdown:**")
                for s in subjs:
                    lines.append(f"- **{s['subject_code']}** ({s['subject_title']}): **{s['attendance_percentage']}%** ({s['classes_attended']}/{s['classes_conducted']}) — Status: {s['status']}")

            return "\n".join(lines)

        elif intent == 'get_low_attendance_students':
            thresh = res.get('threshold_used', 75.0)
            count = res.get('low_attendance_count', 0)
            students = res.get('students', [])
            dept_filt = res.get('department_filter')

            dept_clause = f" in {dept_filt}" if dept_filt else ""
            if count == 0:
                return f"No students{dept_clause} have attendance below the {thresh}% threshold. All evaluated students meet or exceed the attendance requirements."

            lines = [
                f"There are **{count} student(s)**{dept_clause} strictly below the **{thresh}%** attendance threshold:",
                ""
            ]
            for idx, s in enumerate(students, 1):
                lines.append(
                    f"{idx}. **{s['name']}** ({s['roll_number']}) — {s['department_code']} Sec {s['section']}: "
                    f"**{s['overall_percentage']}%** ({s['total_attended']}/{s['total_conducted']} attended). "
                    f"Needs **+{s['classes_needed_to_reach_threshold']} consecutive classes** to recover."
                )
            return "\n".join(lines)

        elif intent == 'get_subject_attendance':
            # Specific subject
            if params.get('subject_code'):
                subjs = res.get('subjects', [])
                if not subjs:
                    return f"No data found for subject {params.get('subject_code')}."
                s = subjs[0]
                if not s['has_classes']:
                    return f"Subject **{s['code']} - {s['title']}** currently has no recorded attendance sessions."
                return (
                    f"Subject **{s['code']} - {s['title']}** ({s['department_name']}):\n"
                    f"- **Average Attendance:** **{s['average_attendance_percentage']}%**\n"
                    f"- **Sessions Conducted:** {s['total_sessions_conducted']}\n"
                    f"- **Student Records:** {s['total_attended']} attended out of {s['total_records_evaluated']} total"
                )

            # Lowest subject comparison
            lowest = res.get('lowest_attendance_subject')
            highest = res.get('highest_attendance_subject')
            if not lowest:
                return "No recorded attendance sessions were found for any subjects in university courses."

            lines = [
                f"The subject with the **lowest attendance** is **{lowest['code']} - {lowest['title']}** with an average attendance of **{lowest['average_attendance_percentage']}%** ({lowest['total_attended']}/{lowest['total_records_evaluated']} student attendances across {lowest['total_sessions_conducted']} sessions).",
            ]
            if highest and highest['code'] != lowest['code']:
                lines.append(f"In comparison, the highest attendance course is **{highest['code']} - {highest['title']}** at **{highest['average_attendance_percentage']}%**.")

            active_subjs = [s for s in res.get('subjects', []) if s['has_classes']]
            if len(active_subjs) > 1:
                lines.append("\n**Subject Attendance Ranking (Lowest to Highest):**")
                for idx, s in enumerate(active_subjs, 1):
                    lines.append(f"{idx}. **{s['code']}**: {s['average_attendance_percentage']}% ({s['total_sessions_conducted']} sessions)")

            return "\n".join(lines)

        elif intent == 'get_department_attendance':
            lowest = res.get('lowest_attendance_department')
            highest = res.get('highest_attendance_department')
            if not lowest:
                return "No departmental attendance sessions have been conducted yet across the university."

            lines = [
                f"The department with the **lowest attendance** is **{lowest['department_name']} ({lowest['department_code']})** with **{lowest['attendance_percentage']}%** attendance ({lowest['total_attended']}/{lowest['total_records_evaluated']} attendances recorded across {lowest['total_sessions_conducted']} sessions).",
            ]
            if highest and highest['department_code'] != lowest['department_code']:
                lines.append(f"The highest attendance is in **{highest['department_name']} ({highest['department_code']})** at **{highest['attendance_percentage']}%**.")

            active_depts = [d for d in res.get('departments', []) if d['has_classes']]
            if active_depts:
                lines.append("\n**Department Breakdown (Active Cohorts):**")
                for d in active_depts:
                    lines.append(f"- **{d['department_name']} ({d['department_code']}):** **{d['attendance_percentage']}%** ({d['total_students']} students enrolled, {d['total_faculty']} faculty)")

            inactive_depts = [d for d in res.get('departments', []) if not d['has_classes']]
            if inactive_depts:
                lines.append("\n*Departments with no sessions conducted yet: " + ", ".join([d['department_name'] for d in inactive_depts]) + "*")

            return "\n".join(lines)

        elif intent == 'get_attendance_history':
            total = res.get('total_matching_records', 0)
            days = res.get('days_window', 30)
            if total == 0:
                return f"No attendance history records were found in the last {days} days."

            records = res.get('records', [])
            lines = [
                f"Found **{total} attendance record(s)** logged over the last {days} days:",
                ""
            ]
            for r in records[:10]:
                lines.append(
                    f"- **{r['session_date']}** (P{r['period_number']}) — **{r['subject_code']}**: "
                    f"Student {r['student_name']} ({r['student_roll_number']}) marked **{r['status']}** by Prof. {r['faculty_name']}"
                )
            if total > 10:
                lines.append(f"\n*(Showing 10 of {total} records)*")
            return "\n".join(lines)

        elif intent == 'get_attendance_statistics':
            curr = res.get('current_window', {})
            prev = res.get('previous_window', {})
            pct = curr.get('attendance_percentage', 0.0)
            sessions = curr.get('sessions_conducted', 0)
            tot_rec = curr.get('total_student_records', 0)
            change = res.get('percentage_change', 0.0)
            direction = res.get('trend_direction', 'stable')
            time_frame = res.get('time_frame', 'month')

            if tot_rec == 0:
                return f"No attendance sessions were conducted during the current {time_frame} timeframe."

            change_str = f"+{change}%" if change > 0 else f"{change}%"
            lines = [
                f"**Attendance Trend Summary ({time_frame.capitalize()}):**",
                f"- **Current Attendance:** **{pct}%** across **{sessions} conducted sessions** ({tot_rec} student attendances evaluated).",
            ]
            if prev.get('total_student_records', 0) > 0:
                lines.append(f"- **Comparison with Previous {time_frame.capitalize()}:** Changed by **{change_str}** (Trend: **{direction}** from {prev.get('attendance_percentage', 0.0)}%).")
            else:
                lines.append(f"- **Historical Comparison:** No recorded sessions in the previous {time_frame} period for baseline comparison.")

            trends = res.get('daily_trends', [])
            if trends:
                lines.append("\n**Recent Session Timeline:**")
                for t in trends:
                    lines.append(f"- **{t['date']}:** {t['attendance_percentage']}% ({t['sessions_conducted']} session(s))")

            return "\n".join(lines)

        return res.get('message', "Attendance query processed successfully.")
