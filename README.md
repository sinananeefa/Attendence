# Edumerge Smart Attendance Management

A role-based attendance management prototype for academic institutions. The system supports attendance recording, corrections, review, history, low-attendance identification, dashboards, and an AI assistant over verified attendance data.

## Working Prototype

- Frontend: React, TypeScript, Vite
- Backend: Django, Django REST Framework
- Authentication: JWT with Django password hashing
- Database: SQLite for the included prototype; MySQL can be enabled through environment configuration
- Local frontend: `http://localhost:5175/`
- Local API: `http://127.0.0.1:8000/`

## Roles and Workflows

- Administrator: manages academic structure, users, policies, reports, and dashboards.
- HOD: views department-scoped academic and attendance information.
- Faculty/Mentor: views allocations, rosters, records attendance, reviews corrections, and monitors low attendance.
- Student: views attendance history, summaries, warnings, and submits correction requests.

New self-registered accounts are restricted to the `STUDENT` role. Academic identity fields such as section, roll number, and course enrollment are assigned separately by an authorized administrator. The UI shows a clear profile-pending state until those records exist; it does not create fabricated academic data.

## Architecture

The React frontend communicates with REST endpoints under `/api`. Django owns authentication, authorization, validation, academic relationships, attendance calculations, correction workflows, audit logs, and AI tool access.

Core backend areas:

- `accounts`: users, roles, registration, login, JWT sessions, and permissions.
- `academic`: departments, programs, years, semesters, classes, sections, subjects, students, faculty, and enrollments.
- `attendance`: sessions, records, calculations, corrections, audit logs, dashboards, and low-attendance reports.
- `ai_assistant`: read-only assistant service and attendance tools.

## Important Engineering Decisions

- Passwords are always stored through Django's password hasher, never as plain text.
- Privileged roles cannot be selected during public registration.
- Attendance corrections preserve the original record and create immutable audit history.
- Attendance percentages are calculated by backend services rather than trusted frontend values.
- API permissions are enforced server-side; frontend role visibility is not treated as security.
- Development quick-login accounts are visible only in Vite development mode and are absent from production assets.
- SQLite keeps the prototype easy to run. MySQL settings are environment-driven for deployment without committing credentials.

## Assumptions

- An administrator provisions faculty, HOD, mentor, and student academic assignments.
- A student account and a student academic profile are separate records because enrollment requires institutional verification.
- Attendance is recorded against faculty allocations, subjects, sections, periods, and dates.
- The configured attendance threshold is the institutional default unless a subject or report policy overrides it.
- The included seed command provides representative development data only.

## Trade-offs

- SQLite was retained for reproducible local evaluation rather than requiring a running MySQL service.
- JWT keeps the SPA authentication flow simple, while token refresh and expiry remain deployment concerns.
- The AI assistant uses controlled read-only tools instead of unrestricted database access, limiting scope but improving safety and predictability.
- The prototype uses inline styles in some existing dashboard components for speed of iteration; shared theme tokens are used for the main visual system.

## Validation

Verified during final audit:

- Django test suite: `109/109` tests passed.
- Frontend TypeScript check and production build passed with `npm run build`.
- Live registration created a student account with a hashed password and returned a working JWT.
- Live `/auth/me/` accepted the returned token.
- Admin login succeeded against the running API.
- Removed role-switch endpoint returned `404`.
- Browser registration and profile-pending student flow were verified.
- Responsive login layout was checked at desktop and mobile widths.
- Production frontend assets contained no development demo passwords.

Important edge cases covered include duplicate usernames/emails, weak or mismatched passwords, inactive accounts, unauthorized role access, missing student profiles, missing faculty allocations, duplicate attendance submissions, invalid dates and periods, invalid academic relationships, correction approval/rejection, and low-attendance thresholds.

## Recommended Demo Flow

1. Use the development-only quick-fill Administrator account and open the admin dashboard.
2. Show the academic hierarchy: departments, programs, classes, sections, subjects, faculty, and students.
3. Sign in as Faculty and open an allocated class roster.
4. Record attendance, demonstrate duplicate and invalid submission protection, then review history.
5. Sign in as Student and show attendance summary, history, warning status, and correction submission.
6. Approve or reject the correction as Faculty and show the audit trail.
7. Open the low-attendance report and ask the AI assistant for a read-only attendance summary.
8. Create a new account to demonstrate authentication and the profile-pending state.

## Mandatory AI Usage Report

**AI TOOL USED:** GitHub Copilot

**WHAT I ASKED AI TO DO:**

1. Audit the implemented application against the Edumerge Assignment 1 requirements and run the available validation suites.
2. Trace and correct authentication, registration, authorization, and student profile onboarding behavior.
3. Improve the login and dashboard UI/UX, validate responsive behavior, and prepare the repository for submission.

**PROMPT THAT WAS MOST USEFUL:**

“Perform a final audit against the original Edumerge Assignment 1 requirements. Do not claim something works unless you actually verify it. Run the complete application test and list bugs, fixes, limitations, and a recommended demo flow.”

**CODE GENERATED BY AI:**

Focused changes in the authentication flow, profile-pending dashboard state, login autofill/demo controls, shared theme tokens, responsive login styling, and submission documentation were generated or edited with Copilot assistance.

**CODE I MODIFIED:**

The existing Django models, API workflows, React dashboards, and tests were reviewed and modified in the current workspace. Changes were kept compatible with the existing architecture and validated against the existing test suite.

**AI OUTPUT THAT WAS WRONG:**

The first live browser diagnosis treated the login failure as an application authentication defect. The source code was correct; the running Django process was stale and still served the previous URL configuration. A later browser check also exposed that a newly registered student had no academic profile, which was a data-assignment state rather than an authentication failure.

**HOW I IDENTIFIED THE PROBLEM:**

I called the live registration endpoint directly, inspected the returned URL patterns, checked the process bound to port `8000`, and compared the live behavior with the current source. I then reproduced registration and `/auth/me/` using the restarted backend and verified the browser flow.

**HOW I FIXED IT:**

I restarted the backend using the current source, removed the obsolete role-switch path from the implementation, preserved hashed-password registration, and changed the student dashboard to present a clear academic-profile-pending state instead of a generic error. The final tests and browser checks passed.

## Source Repository

https://github.com/sinananeefa/Attendence

## Submission Note

This repository contains the working prototype and source code. The implementation, assumptions, trade-offs, validation evidence, and AI usage are documented here for technical/product evaluation.
