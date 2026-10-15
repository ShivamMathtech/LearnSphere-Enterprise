import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { AuthProvider, useAuth } from "./Auth";
import { Shell } from "../layouts/Shell";
import { Loading, Empty } from "../components/UI";
import { LoginPage, RecoveryPage, VerifyPage } from "../pages/AuthPages";
import { Dashboard } from "../pages/Dashboard";
import {
  CourseCatalog,
  CourseDetail,
  CourseEditor,
  LearningPage,
  LearningPlayer,
} from "../pages/Courses";
import { AssessmentsPage, AttemptPage } from "../pages/Assessments";
import {
  AcademicsPage,
  EnrollmentsPage,
  InstitutionsPage,
  RolesPage,
  UsersPage,
} from "../pages/Admin";
import {
  AttendancePage,
  CommunityPage,
  NotificationsPage,
} from "../pages/Community";
import {
  AuditPage,
  CertificatesPage,
  ProfilePage,
  ReportsPage,
  SettingsPage,
} from "../pages/Operations";
function SignedIn() {
  const { user, loading } = useAuth();
  return loading ? (
    <Loading />
  ) : user ? (
    <Shell />
  ) : (
    <Navigate to="/login" replace />
  );
}
function Guard({
  permission,
  children,
}: {
  permission: string;
  children: ReactNode;
}) {
  const { can } = useAuth();
  return can(permission) ? (
    <>{children}</>
  ) : (
    <div className="panel">
      <Empty>Your role does not have access to this area.</Empty>
    </div>
  );
}
export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/forgot-password"
            element={<RecoveryPage mode="forgot" />}
          />
          <Route
            path="/reset-password"
            element={<RecoveryPage mode="reset" />}
          />
          <Route
            path="/verify-email"
            element={<RecoveryPage mode="verify" />}
          />
          <Route path="/verify/:code" element={<VerifyPage />} />
          <Route element={<SignedIn />}>
            <Route index element={<Dashboard />} />
            <Route
              path="courses"
              element={
                <Guard permission="courses.read">
                  <CourseCatalog />
                </Guard>
              }
            />
            <Route
              path="courses/new"
              element={
                <Guard permission="courses.create">
                  <CourseEditor />
                </Guard>
              }
            />
            <Route
              path="courses/:id/edit"
              element={
                <Guard permission="courses.update">
                  <CourseEditor />
                </Guard>
              }
            />
            <Route
              path="courses/:id"
              element={
                <Guard permission="courses.read">
                  <CourseDetail />
                </Guard>
              }
            />
            <Route
              path="learning"
              element={
                <Guard permission="progress.update">
                  <LearningPage />
                </Guard>
              }
            />
            <Route
              path="learn/:id"
              element={
                <Guard permission="progress.update">
                  <LearningPlayer />
                </Guard>
              }
            />
            <Route
              path="assessments"
              element={
                <Guard permission="courses.read">
                  <AssessmentsPage />
                </Guard>
              }
            />
            <Route
              path="attempts/:id"
              element={
                <Guard permission="courses.read">
                  <AttemptPage />
                </Guard>
              }
            />
            <Route
              path="users"
              element={
                <Guard permission="users.read">
                  <UsersPage />
                </Guard>
              }
            />
            <Route
              path="academics"
              element={
                <Guard permission="academic.read">
                  <AcademicsPage />
                </Guard>
              }
            />
            <Route
              path="institutions"
              element={
                <Guard permission="institutions.manage">
                  <InstitutionsPage />
                </Guard>
              }
            />
            <Route
              path="roles"
              element={
                <Guard permission="roles.read">
                  <RolesPage />
                </Guard>
              }
            />
            <Route
              path="enrollments"
              element={
                <Guard permission="enrollments.manage">
                  <EnrollmentsPage />
                </Guard>
              }
            />
            <Route
              path="attendance"
              element={
                <Guard permission="courses.read">
                  <AttendancePage />
                </Guard>
              }
            />
            <Route
              path="community"
              element={
                <Guard permission="courses.read">
                  <CommunityPage />
                </Guard>
              }
            />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route
              path="certificates"
              element={
                <Guard permission="certificates.read">
                  <CertificatesPage />
                </Guard>
              }
            />
            <Route
              path="reports"
              element={
                <Guard permission="reports.read">
                  <ReportsPage />
                </Guard>
              }
            />
            <Route
              path="audit"
              element={
                <Guard permission="audit.read">
                  <AuditPage />
                </Guard>
              }
            />
            <Route
              path="settings"
              element={
                <Guard permission="settings.manage">
                  <SettingsPage />
                </Guard>
              }
            />
            <Route path="profile" element={<ProfilePage />} />
            <Route
              path="*"
              element={<Empty>This page could not be found.</Empty>}
            />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
