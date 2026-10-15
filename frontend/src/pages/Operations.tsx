import { useState } from "react";
import { Link } from "react-router-dom";
import { Award, Download, ShieldCheck } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { useAuth } from "../app/Auth";
import { useApi, useAction } from "../hooks/api";
import {
  ActionButton,
  Badge,
  DataForm,
  Empty,
  ErrorBox,
  Heading,
  Loading,
  Modal,
  Table,
  text,
  date,
} from "../components/UI";
import { download, send } from "../services/api";
import type { Entity, Page, User } from "../types/domain";
export function CertificatesPage() {
  const [page, setPage] = useState(1),
    [selected, setSelected] = useState<Entity | null>(null),
    query = useApi<Page>(`/certificates?page=${page}`),
    enrollments = useApi<Page>("/enrollments?page_size=100"),
    action = useAction(),
    { can } = useAuth();
  return (
    <>
      <Heading
        title="Achievements, made official"
        description="Your learning deserves recognition. Every certificate can be independently verified."
      />
      <ErrorBox error={query.error} />
      <div className="certificate-grid">
        {query.data?.items.map((c) => (
          <article className="panel certificate-card" key={c.id}>
            <div className="certificate-mark">
              <Award size={43} />
            </div>
            <span className="eyebrow">CERTIFICATE OF COMPLETION</span>
            <h2>{text(c, "course_title")}</h2>
            <p>{text(c, "student_name")}</p>
            <small>
              {text(c, "issuer")} · {date(c.created_at)}
            </small>
            <Badge>{c.revoked_at ? "revoked" : "valid"}</Badge>
            <div className="actions">
              <ActionButton
                onClick={() =>
                  download(
                    `/certificates/${c.id}/pdf`,
                    `${text(c, "course_title").replaceAll(" ", "-")}-certificate.pdf`,
                  )
                }
              >
                <Download size={15} /> PDF
              </ActionButton>
              <Link
                className="button small"
                to={`/verify/${text(c, "code")}`}
                target="_blank"
              >
                Verify
              </Link>
              {can("certificates.manage") && !c.revoked_at && (
                <button className="button small" onClick={() => setSelected(c)}>
                  Revoke
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
      {query.data?.total === 0 && (
        <div className="panel">
          <Empty>
            Complete a course’s requirements to earn your first certificate.
          </Empty>
        </div>
      )}
      <div className="pagination">
        <span>Page {page}</span>
        <div className="actions">
          <button
            className="button"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </button>
          <button
            className="button"
            disabled={!query.data || page * 20 >= query.data.total}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </div>
      <section className="panel info-panel">
        <h2>Request a certificate</h2>
        <p className="muted">
          Eligibility is checked against completed lessons and passing required
          assessments.
        </p>
        <DataForm
          fields={[
            {
              name: "enrollment_id",
              label: "Enrollment",
              type: "select",
              required: true,
              options: enrollments.data?.items.map((e) => ({
                value: e.id,
                label: `${text(e, "student_name")} · ${text(e, "course_title")}`,
              })),
            },
          ]}
          label="Check eligibility and issue"
          onSubmit={(v) =>
            action.mutateAsync({
              path: `/certificates/issue/${v.enrollment_id}`,
            })
          }
        />
      </section>
      {selected && (
        <Modal title="Revoke certificate" onClose={() => setSelected(null)}>
          <DataForm
            fields={[
              {
                name: "reason",
                label: "Reason for revocation",
                type: "textarea",
                required: true,
              },
            ]}
            label="Revoke certificate"
            onSubmit={async (v) => {
              if (
                confirm(
                  "Revoke this certificate? Public verification will show it as revoked.",
                )
              ) {
                await action.mutateAsync({
                  path: `/certificates/${selected.id}/revoke`,
                  body: v,
                });
                setSelected(null);
              }
            }}
          />
        </Modal>
      )}
    </>
  );
}
export function ReportsPage() {
  const [page, setPage] = useState(1),
    [start, setStart] = useState(""),
    [end, setEnd] = useState("");
  const range = `${start ? "&start=" + encodeURIComponent(new Date(start).toISOString()) : ""}${end ? "&end=" + encodeURIComponent(new Date(end + "T23:59:59").toISOString()) : ""}`;
  const query = useApi<Page>(`/reports/enrollments?page=${page}${range}`),
    academic = useApi<{
      departments: {
        department: string;
        enrollments: number;
        completed: number;
      }[];
      quiz_outcomes: {
        title: string;
        average_percent: number;
        attempts: number;
      }[];
    }>("/reports/academic");
  return (
    <>
      <Heading
        title="From activity to insight"
        description="Understand participation, learning outcomes and institutional progress."
      />
      <div className="panel report-filters">
        <label>
          From
          <input
            type="date"
            value={start}
            onChange={(e) => {
              setStart(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          To
          <input
            type="date"
            value={end}
            onChange={(e) => {
              setEnd(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <div className="actions">
          {["enrollments", "grades", "attendance"].map((kind) => (
            <ActionButton
              key={kind}
              onClick={() =>
                download(
                  `/reports/export.csv?kind=${kind}${range}`,
                  `${kind}.csv`,
                )
              }
            >
              <Download size={15} /> {kind}
            </ActionButton>
          ))}
        </div>
      </div>
      <div className="assessment-grid">
        <section className="panel chart-panel">
          <h2>Participation by department</h2>
          {academic.data?.departments.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={academic.data.departments}
                margin={{ left: -20, right: 10, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="department" fontSize={11} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar
                  dataKey="enrollments"
                  fill="#159b8d"
                  radius={[5, 5, 0, 0]}
                />
                <Bar dataKey="completed" fill="#9690ce" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Empty>No departmental learning activity yet.</Empty>
          )}
        </section>
        <section className="panel info-panel">
          <h2>Quiz outcomes</h2>
          {academic.data?.quiz_outcomes.map((q) => (
            <div className="assessment-row" key={q.title}>
              <div>
                <h3>{q.title}</h3>
                <p>{q.attempts} graded attempts</p>
              </div>
              <strong>{q.average_percent}% average</strong>
            </div>
          ))}
          {academic.data?.quiz_outcomes.length === 0 && (
            <Empty>Graded quiz results will appear here.</Empty>
          )}
          <ErrorBox error={academic.error} />
        </section>
      </div>
      <Table
        data={query.data}
        loading={query.isLoading}
        error={query.error}
        page={page}
        setPage={setPage}
        columns={[
          { key: "student_name", label: "Learner" },
          { key: "course_title", label: "Course" },
          {
            key: "status",
            label: "Status",
            render: (r) => <Badge>{text(r, "status")}</Badge>,
          },
          {
            key: "progress",
            label: "Progress",
            render: (r) => `${r.progress}%`,
          },
        ]}
      />
    </>
  );
}
export function AuditPage() {
  const [page, setPage] = useState(1),
    [search, setSearch] = useState(""),
    query = useApi<Page>(
      `/audit-logs?page=${page}&search=${encodeURIComponent(search)}`,
    );
  return (
    <>
      <Heading
        title="A clear record of every change"
        description="Review security, administrative and learning-record events."
      />
      <Table
        data={query.data}
        loading={query.isLoading}
        error={query.error}
        page={page}
        setPage={setPage}
        search={search}
        setSearch={setSearch}
        columns={[
          {
            key: "created_at",
            label: "When",
            render: (r) => date(r.created_at),
          },
          {
            key: "action",
            label: "Event",
            render: (r) => <code>{text(r, "action")}</code>,
          },
          { key: "resource_type", label: "Resource" },
          {
            key: "actor_id",
            label: "Actor",
            render: (r) => (
              <code title={text(r, "actor_id")}>
                {text(r, "actor_id").slice(0, 8) || "Anonymous"}
              </code>
            ),
          },
          {
            key: "detail",
            label: "Change details",
            render: (r) => (
              <span className="small-json">{JSON.stringify(r.detail)}</span>
            ),
          },
        ]}
      />
    </>
  );
}
export function SettingsPage() {
  const status = useApi<Entity>("/system/status"),
    settings = useApi<Entity[]>("/settings"),
    action = useAction();
  const certificate = settings.data?.find((s) => s.key === "certificate");
  return (
    <>
      <Heading
        title="Institution configuration"
        description="Branding, certificate presentation and integration status."
      />
      <ErrorBox error={status.error} />
      <div className="panel info-panel">
        <h2>System & integration status</h2>
        <div className="system-grid">
          {status.data &&
            Object.entries(status.data).map(([key, value]) => (
              <div key={key}>
                <small>{key.replaceAll("_", " ")}</small>
                <strong>
                  {typeof value === "object"
                    ? JSON.stringify(value)
                    : String(value)}
                </strong>
              </div>
            ))}
        </div>
        <p className="muted">
          SMTP and security policies are configured through backend environment
          variables. Meeting links use the supported manual workflow; plagiarism
          checking requires a provider adapter.
        </p>
      </div>
      <div className="assessment-grid">
        <section className="panel info-panel">
          <h2>Certificate template</h2>
          {!settings.isLoading && (
            <DataForm
              fields={[
                {
                  name: "heading",
                  label: "Heading",
                  default: "Certificate of Completion",
                },
                { name: "issuer", label: "Authorized issuer", required: true },
                { name: "footer", label: "Footer text" },
              ]}
              initial={(certificate?.value as Record<string, unknown>) || {}}
              onSubmit={(v) =>
                action.mutateAsync({
                  path: "/settings/certificate",
                  method: "PUT",
                  body: { value: v },
                })
              }
            />
          )}
        </section>
        <section className="panel info-panel">
          <h2>Institution branding</h2>
          {!settings.isLoading && (
            <DataForm
              fields={[
                { name: "display_name", label: "Display name", required: true },
                {
                  name: "accent",
                  label: "Brand accent (hex)",
                  default: "#159b8d",
                },
                {
                  name: "support_email",
                  label: "Support email",
                  type: "email",
                  required: true,
                },
              ]}
              initial={
                (settings.data?.find((s) => s.key === "branding")
                  ?.value as Record<string, unknown>) || {}
              }
              onSubmit={(v) =>
                action.mutateAsync({
                  path: "/settings/branding",
                  method: "PUT",
                  body: { value: v },
                })
              }
            />
          )}
        </section>
      </div>
    </>
  );
}
export function ProfilePage() {
  const auth = useAuth(),
    profile = useApi<User & { bio: string; timezone: string }>("/auth/profile"),
    sessions = useApi<Entity[]>("/auth/sessions"),
    action = useAction(),
    [mfa, setMfa] = useState<{ secret: string; uri: string } | null>(null);
  return (
    <>
      <Heading
        title="Your profile & security"
        description="Make the workspace yours, and keep your account protected."
      />
      <div className="assessment-grid">
        <section className="panel info-panel">
          <h2>Personal details</h2>
          {profile.isLoading ? (
            <Loading />
          ) : (
            profile.data && (
              <DataForm
                fields={[
                  { name: "name", label: "Full name", required: true },
                  { name: "bio", label: "About you", type: "textarea" },
                  {
                    name: "timezone",
                    label: "Display timezone",
                    required: true,
                    default: "Asia/Kolkata",
                  },
                ]}
                initial={{ ...profile.data }}
                onSubmit={async (v) => {
                  await action.mutateAsync({
                    path: "/auth/profile",
                    method: "PUT",
                    body: v,
                  });
                  await auth.reload();
                }}
              />
            )
          )}
          <ErrorBox error={profile.error} />
        </section>
        <section className="panel info-panel">
          <h2>
            <ShieldCheck size={20} /> Change password
          </h2>
          <p className="muted">
            Changing your password revokes all active sessions.
          </p>
          <DataForm
            fields={[
              {
                name: "current_password",
                label: "Current password",
                type: "password",
                required: true,
              },
              {
                name: "password",
                label: "New password",
                type: "password",
                required: true,
                help: "12–128 characters with uppercase, lowercase and a number.",
              },
            ]}
            onSubmit={async (v) => {
              await send("/auth/change-password", v);
              window.dispatchEvent(new Event("session-expired"));
            }}
          />
        </section>
      </div>
      <section className="panel info-panel">
        <h2>Two-step verification</h2>
        <p className="muted">
          Use an authenticator app to protect sign-ins. Status:{" "}
          {auth.user?.mfa_enabled ? "Enabled" : "Not enabled"}
        </p>
        {!auth.user?.mfa_enabled && !mfa && (
          <DataForm
            fields={[
              {
                name: "current_password",
                label: "Confirm your password",
                type: "password",
                required: true,
              },
            ]}
            label="Set up authenticator"
            onSubmit={async (v) => setMfa(await send("/auth/mfa/setup", v))}
          />
        )}{" "}
        {mfa && (
          <>
            <div className="info-box">
              <p>
                Enter this secret in your authenticator app, then confirm a
                current code.
              </p>
              <code className="mfa-secret">{mfa.secret}</code>
              <a className="text-link" href={mfa.uri}>
                Open authenticator app
              </a>
            </div>
            <DataForm
              fields={[
                {
                  name: "password",
                  label: "Password",
                  type: "password",
                  required: true,
                },
                {
                  name: "code",
                  label: "Six-digit authenticator code",
                  required: true,
                },
              ]}
              label="Enable verification"
              onSubmit={async (v) => {
                await send("/auth/mfa/enable", v);
                setMfa(null);
                await auth.reload();
              }}
            />
          </>
        )}
        {auth.user?.mfa_enabled && (
          <DataForm
            fields={[
              {
                name: "password",
                label: "Password",
                type: "password",
                required: true,
              },
              {
                name: "code",
                label: "Current authenticator code",
                required: true,
              },
            ]}
            label="Disable two-step verification"
            onSubmit={async (v) => {
              if (
                confirm(
                  "Disable two-step verification? All sessions will be revoked.",
                )
              ) {
                await send("/auth/mfa/disable", v);
                window.dispatchEvent(new Event("session-expired"));
              }
            }}
          />
        )}
      </section>
      <section className="panel info-panel">
        <h2>Sign-in sessions</h2>
        <ErrorBox error={sessions.error} />
        {sessions.data?.map((s) => (
          <div className="assessment-row" key={s.id}>
            <div>
              <strong>
                {s.current ? "This session" : "Session"}{" "}
                <Badge>{s.revoked ? "revoked" : "active"}</Badge>
              </strong>
              <p>{text(s, "user_agent") || "API client"}</p>
              <small>
                Created {date(s.created_at)} · Expires {date(s.expires_at)}
              </small>
            </div>
            {!s.revoked && (
              <ActionButton
                onClick={async () => {
                  await action.mutateAsync({
                    path: `/auth/sessions/${s.id}`,
                    method: "DELETE",
                  });
                  if (s.current)
                    window.dispatchEvent(new Event("session-expired"));
                }}
              >
                Revoke
              </ActionButton>
            )}
          </div>
        ))}
      </section>
    </>
  );
}
