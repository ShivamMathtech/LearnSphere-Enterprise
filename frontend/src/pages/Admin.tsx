import { useState } from "react";
import { Plus, Upload, Shield, Download } from "lucide-react";
import { useAuth } from "../app/Auth";
import { useApi, useAction } from "../hooks/api";
import {
  ActionButton,
  Badge,
  DataForm,
  ErrorBox,
  Heading,
  Loading,
  Modal,
  Table,
  text,
  type Field,
} from "../components/UI";
import { download, send } from "../services/api";
import type { Entity, Page, Course } from "../types/domain";
const roles = [
  "student",
  "instructor",
  "teaching_assistant",
  "coordinator",
  "auditor",
];
export function UsersPage() {
  const [page, setPage] = useState(1),
    [search, setSearch] = useState(""),
    [modal, setModal] = useState(""),
    [selected, setSelected] = useState<Entity | null>(null);
  const auth = useAuth(),
    query = useApi<Page>(
      `/users?page=${page}&search=${encodeURIComponent(search)}`,
    ),
    departments = useApi<Page>(
      "/departments?page_size=100",
      auth.can("academic.read"),
    ),
    action = useAction();
  const roleOptions = [
    ...roles,
    ...(auth.user?.roles.includes("super_admin") ? ["institution_admin"] : []),
  ].map((value) => ({ value, label: value.replaceAll("_", " ") }));
  const fields: Field[] = [
    { name: "name", label: "Full name", required: true },
    { name: "email", label: "Email address", type: "email", required: true },
    {
      name: "role",
      label: "Role",
      type: "select",
      options: roleOptions,
      default: "student",
    },
    {
      name: "password",
      label: "Initial password",
      type: "password",
      help: "Leave blank when sending an invitation.",
    },
    { name: "invite", label: "Send an invitation instead", type: "checkbox" },
    { name: "identifier", label: "Student / faculty identifier" },
    {
      name: "department_id",
      label: "Department",
      type: "select",
      options: departments.data?.items.map((d) => ({
        value: d.id,
        label: text(d, "name"),
      })),
    },
  ];
  return (
    <>
      <Heading
        title="People & access"
        description="The people at the heart of your learning community."
      >
        {auth.can("imports.manage") && (
          <button className="button" onClick={() => setModal("import")}>
            <Upload size={16} /> Import CSV
          </button>
        )}
        {auth.can("users.create") && (
          <button
            className="button primary"
            onClick={() => {
              setSelected(null);
              setModal("create");
            }}
          >
            <Plus size={17} /> Add person
          </button>
        )}
      </Heading>
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
            key: "name",
            label: "Name",
            render: (r) => (
              <div className="person-cell">
                <span className="avatar">{text(r, "name").slice(0, 1)}</span>
                <div>
                  <strong>{text(r, "name")}</strong>
                  <small>{text(r, "email")}</small>
                </div>
              </div>
            ),
          },
          {
            key: "roles",
            label: "Role",
            render: (r) => <Badge>{(r.roles as string[]).join(", ")}</Badge>,
          },
          { key: "identifier", label: "Institution ID" },
          {
            key: "active",
            label: "Status",
            render: (r) => <Badge>{r.active ? "active" : "disabled"}</Badge>,
          },
        ]}
        actions={
          auth.can("users.update")
            ? (r) => (
                <>
                  <button
                    className="button small"
                    onClick={() => {
                      setSelected(r);
                      setModal("edit");
                    }}
                  >
                    Edit
                  </button>
                  <button
                    className="button small"
                    onClick={() => {
                      setSelected(r);
                      setModal("role");
                    }}
                  >
                    Role
                  </button>
                  <ActionButton
                    onClick={async () => {
                      if (
                        confirm(
                          `${r.active ? "Disable" : "Enable"} ${text(r, "name")}?`,
                        )
                      )
                        await action.mutateAsync({
                          path: `/users/${r.id}`,
                          method: "PATCH",
                          body: { active: !r.active },
                        });
                    }}
                  >
                    {r.active ? "Disable" : "Enable"}
                  </ActionButton>
                </>
              )
            : undefined
        }
      />
      {modal === "create" && (
        <Modal title="Add an institution member" onClose={() => setModal("")}>
          <DataForm
            fields={fields}
            label="Create account"
            onSubmit={async (v) => {
              await action.mutateAsync({
                path: "/users",
                body: {
                  ...v,
                  password: v.password || null,
                  identifier: v.identifier || null,
                },
              });
              setModal("");
            }}
          />
        </Modal>
      )}
      {modal === "edit" && selected && (
        <Modal title="Edit member" onClose={() => setModal("")}>
          <DataForm
            fields={fields.filter((f) =>
              ["name", "identifier", "department_id"].includes(f.name),
            )}
            initial={selected}
            onSubmit={async (v) => {
              await action.mutateAsync({
                path: `/users/${selected.id}`,
                body: v,
                method: "PATCH",
              });
              setModal("");
            }}
          />
        </Modal>
      )}
      {modal === "role" && selected && (
        <Modal title="Change role" onClose={() => setModal("")}>
          <p className="muted">
            The new role replaces the existing role and revokes active sessions.
          </p>
          <DataForm
            fields={[
              {
                name: "role",
                label: "Role",
                type: "select",
                options: roleOptions,
                required: true,
              },
            ]}
            onSubmit={async (v) => {
              await action.mutateAsync({
                path: `/users/${selected.id}/role`,
                body: v,
                method: "PUT",
              });
              setModal("");
            }}
          />
        </Modal>
      )}
      {modal === "import" && <ImportDialog close={() => setModal("")} />}
    </>
  );
}
function ImportDialog({ close }: { close: () => void }) {
  const [csv, setCsv] = useState(""),
    [headers, setHeaders] = useState<string[]>([]),
    [mapping, setMapping] = useState<Record<string, string>>({}),
    [role, setRole] = useState("student"),
    [preview, setPreview] = useState<{
      rows: Entity[];
      errors: { line: number; error: string }[];
      valid_count: number;
      preview_hash: string;
    } | null>(null),
    [message, setMessage] = useState("");
  const action = useAction();
  const payload = { csv_text: csv, mapping, role };
  const load = (value: string) => {
    setCsv(value);
    setHeaders(
      value
        .split(/\r?\n/)[0]
        .split(",")
        .map((h) => h.trim().replaceAll('"', "")),
    );
    setPreview(null);
  };
  return (
    <Modal title="Import students or faculty" onClose={close}>
      <p className="muted">
        Upload a UTF-8 CSV, map its columns, and preview every row before
        committing. Any validation error prevents the entire import.
      </p>
      <label className="field">
        CSV file
        <input
          type="file"
          accept=".csv"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (f) load(await f.text());
          }}
        />
      </label>
      <textarea
        aria-label="CSV content"
        rows={6}
        value={csv}
        onChange={(e) => load(e.target.value)}
        placeholder={
          "Name,Email,Identifier\nAda Lovelace,ada@example.com,STU001"
        }
      />
      <div className="data-form">
        {["name", "email", "identifier"].map((key) => (
          <label className="field" key={key}>
            {key}
            <select
              value={mapping[key] || ""}
              onChange={(e) => {
                const next = { ...mapping };
                if (e.target.value) next[key] = e.target.value;
                else delete next[key];
                setMapping(next);
                setPreview(null);
              }}
            >
              <option value="">Select column</option>
              {headers.map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
          </label>
        ))}
        <label className="field">
          Account type
          <select
            value={role}
            onChange={(e) => {
              setRole(e.target.value);
              setPreview(null);
            }}
          >
            <option value="student">Students</option>
            <option value="instructor">Faculty</option>
          </select>
        </label>
      </div>
      <ActionButton
        onClick={async () =>
          setPreview(await send("/users/import/preview", payload))
        }
      >
        Preview import
      </ActionButton>
      {preview && (
        <>
          <div className="info-box">
            {preview.valid_count} valid rows · {preview.errors.length} errors
          </div>
          <div className="preview-rows">
            {preview.rows.map((r) => (
              <p key={String(r.line)}>
                {String(r.line)} · {String(r.name)} · {String(r.email)}
              </p>
            ))}
            {preview.errors.map((e) => (
              <p className="field-error" key={e.line}>
                Row {e.line}: {e.error}
              </p>
            ))}
          </div>
          <div className="actions">
            <ActionButton
              onClick={() =>
                download(
                  "/users/import/errors.csv",
                  "import-errors.csv",
                  payload,
                )
              }
            >
              <Download size={15} /> Error report
            </ActionButton>
            {!preview.errors.length && (
              <ActionButton
                className="button primary"
                onClick={async () => {
                  await action.mutateAsync({
                    path: "/users/import/commit",
                    body: { ...payload, preview_hash: preview.preview_hash },
                  });
                  setPreview(null);
                  setMessage(
                    "Import completed. Invitations are queued; SMTP must be configured for delivery.",
                  );
                }}
              >
                Import {preview.valid_count} accounts
              </ActionButton>
            )}
          </div>
        </>
      )}
      {message && <div className="success-box">{message}</div>}
    </Modal>
  );
}
const academicNames = {
  departments: "Departments",
  programs: "Programs",
  "academic-years": "Academic years",
  semesters: "Semesters",
  cohorts: "Cohorts",
  "course-categories": "Course categories",
  "course-offerings": "Course offerings",
};
export function AcademicsPage() {
  const [kind, setKind] = useState<keyof typeof academicNames>("departments"),
    [page, setPage] = useState(1),
    [search, setSearch] = useState(""),
    [modal, setModal] = useState(false),
    [selected, setSelected] = useState<Entity | null>(null),
    [membership, setMembership] = useState<Entity | null>(null);
  const query = useApi<Page>(
      `/${kind}?page=${page}&search=${encodeURIComponent(search)}`,
    ),
    deps = useApi<Page>("/departments?page_size=100"),
    programs = useApi<Page>("/programs?page_size=100"),
    years = useApi<Page>("/academic-years?page_size=100"),
    semesters = useApi<Page>("/semesters?page_size=100"),
    cohorts = useApi<Page>("/cohorts?page_size=100"),
    courses = useApi<Page<Course>>("/courses?page_size=100"),
    action = useAction(),
    { can } = useAuth();
  const relation = (
    name: string,
    label: string,
    rows: Entity[] | undefined,
    required = false,
  ): Field => ({
    name,
    label,
    type: "select",
    required,
    options: rows?.map((r) => ({
      value: r.id,
      label: text(r, "name") || text(r, "title"),
    })),
  });
  const fields: Field[] = [{ name: "name", label: "Name", required: true }];
  if (["departments", "programs", "cohorts"].includes(kind))
    fields.push({ name: "code", label: "Code", required: true });
  if (kind === "programs")
    fields.push(relation("department_id", "Department", deps.data?.items), {
      name: "level",
      label: "Academic level",
      default: "Undergraduate",
    });
  if (kind === "academic-years")
    fields.push(
      {
        name: "starts_at",
        label: "Start",
        type: "datetime-local",
        required: true,
      },
      { name: "ends_at", label: "End", type: "datetime-local", required: true },
    );
  if (kind === "semesters")
    fields.push(
      relation("academic_year_id", "Academic year", years.data?.items, true),
    );
  if (kind === "cohorts")
    fields.push(relation("program_id", "Program", programs.data?.items));
  if (kind === "course-offerings")
    fields.push(
      relation("course_id", "Course", courses.data?.items, true),
      relation("cohort_id", "Cohort", cohorts.data?.items, true),
      relation("semester_id", "Semester", semesters.data?.items),
    );
  return (
    <>
      <Heading
        title="Academic structure"
        description="Organize your institution’s programs, cohorts and course delivery."
      >
        {can("academic.manage") && (
          <button
            className="button primary"
            onClick={() => {
              setSelected(null);
              setModal(true);
            }}
          >
            <Plus size={17} /> Add record
          </button>
        )}
      </Heading>
      <div className="tabs">
        {Object.entries(academicNames).map(([key, label]) => (
          <button
            key={key}
            className={kind === key ? "selected" : ""}
            onClick={() => {
              setKind(key as keyof typeof academicNames);
              setPage(1);
              setSearch("");
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <Table
        data={query.data}
        loading={query.isLoading}
        error={query.error}
        page={page}
        setPage={setPage}
        search={search}
        setSearch={setSearch}
        columns={[
          { key: "name", label: academicNames[kind] },
          { key: "code", label: "Code" },
          {
            key: "created_at",
            label: "Created",
            render: (r) => new Date(text(r, "created_at")).toLocaleDateString(),
          },
        ]}
        actions={
          can("academic.manage")
            ? (r) => (
                <>
                  {kind === "cohorts" && (
                    <button
                      className="button small"
                      onClick={() => setMembership(r)}
                    >
                      Members
                    </button>
                  )}
                  <button
                    className="button small"
                    onClick={() => {
                      setSelected(r);
                      setModal(true);
                    }}
                  >
                    Edit
                  </button>
                  <ActionButton
                    onClick={async () => {
                      if (
                        confirm(
                          "Delete this academic record? Referenced records cannot be deleted.",
                        )
                      )
                        await action.mutateAsync({
                          path: `/${kind}/${r.id}`,
                          method: "DELETE",
                        });
                    }}
                  >
                    Delete
                  </ActionButton>
                </>
              )
            : undefined
        }
      />
      {membership && (
        <CohortMembers cohort={membership} close={() => setMembership(null)} />
      )}
      {modal && (
        <Modal
          title={`${selected ? "Edit" : "Add"} ${academicNames[kind].toLowerCase()}`}
          onClose={() => setModal(false)}
        >
          <DataForm
            fields={fields}
            initial={selected || {}}
            onSubmit={async (v) => {
              await action.mutateAsync({
                path: selected ? `/${kind}/${selected.id}` : `/${kind}`,
                method: selected ? "PUT" : "POST",
                body: v,
              });
              setModal(false);
            }}
          />
        </Modal>
      )}
    </>
  );
}
export function InstitutionsPage() {
  const [page, setPage] = useState(1),
    [modal, setModal] = useState(""),
    [selected, setSelected] = useState<Entity | null>(null),
    query = useApi<Page>(`/institutions?page=${page}`),
    action = useAction();
  const fields: Field[] = [
    { name: "name", label: "Institution name", required: true },
    { name: "slug", label: "Unique slug", required: true },
    {
      name: "storage_quota_mb",
      label: "Storage quota (MB)",
      type: "number",
      min: 20,
      max: 1000000,
      default: 1024,
    },
    {
      name: "active",
      label: "Institution active",
      type: "checkbox",
      default: true,
    },
  ];
  return (
    <>
      <Heading
        title="Institutions"
        description="Manage institutional workspaces and appoint their administrators."
      >
        <button
          className="button primary"
          onClick={() => {
            setSelected(null);
            setModal("edit");
          }}
        >
          Add institution
        </button>
      </Heading>
      <Table
        data={query.data}
        loading={query.isLoading}
        error={query.error}
        page={page}
        setPage={setPage}
        columns={[
          { key: "name", label: "Institution" },
          { key: "slug", label: "Slug" },
          { key: "storage_quota_mb", label: "Quota (MB)" },
          { key: "active", label: "Active", render: (r) => String(r.active) },
        ]}
        actions={(r) => (
          <>
            <button
              className="button small"
              onClick={() => {
                setSelected(r);
                setModal("edit");
              }}
            >
              Edit
            </button>
            <button
              className="button small"
              onClick={() => {
                setSelected(r);
                setModal("admin");
              }}
            >
              Add administrator
            </button>
          </>
        )}
      />
      {modal === "edit" && (
        <Modal
          title={selected ? "Edit institution" : "New institution"}
          onClose={() => setModal("")}
        >
          <DataForm
            fields={fields}
            initial={selected || {}}
            onSubmit={async (v) => {
              await action.mutateAsync({
                path: selected
                  ? `/institutions/${selected.id}`
                  : "/institutions",
                method: selected ? "PUT" : "POST",
                body: v,
              });
              setModal("");
            }}
          />
        </Modal>
      )}
      {modal === "admin" && selected && (
        <Modal
          title="Appoint institution administrator"
          onClose={() => setModal("")}
        >
          <DataForm
            fields={[
              { name: "name", label: "Full name", required: true },
              { name: "email", label: "Email", type: "email", required: true },
              {
                name: "password",
                label: "Initial password",
                type: "password",
                required: true,
              },
            ]}
            onSubmit={async (v) => {
              await action.mutateAsync({
                path: `/institutions/${selected.id}/administrator`,
                body: { ...v, role: "institution_admin" },
              });
              setModal("");
            }}
          />
        </Modal>
      )}
    </>
  );
}
export function RolesPage() {
  const query = useApi<Entity[]>("/roles");
  return (
    <>
      <Heading
        title="Roles & permissions"
        description="Explicit capabilities, enforced by the API. Assign member roles from People."
      />
      <ErrorBox error={query.error} />
      {query.isLoading ? (
        <Loading />
      ) : (
        <div className="role-grid">
          {query.data?.map((r) => (
            <section className="panel info-panel" key={r.id}>
              <Shield className="teal" />
              <h2>{text(r, "name").replaceAll("_", " ")}</h2>
              <p>{text(r, "description")}</p>
              <div className="permission-list">
                {(r.permissions as string[]).map((p) => (
                  <code key={p}>{p}</code>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
export function EnrollmentsPage() {
  const [page, setPage] = useState(1),
    [status, setStatus] = useState(""),
    [modal, setModal] = useState(false),
    query = useApi<Page>(`/enrollments?page=${page}&status=${status}`),
    courses = useApi<Page<Course>>("/courses?status=published&page_size=100"),
    users = useApi<Page>("/users?page_size=100"),
    action = useAction();
  return (
    <>
      <Heading
        title="Enrollment management"
        description="Review requests, manage waitlists and open learning opportunities."
      >
        <button className="button primary" onClick={() => setModal(true)}>
          Enroll learners
        </button>
      </Heading>
      <div className="catalog-tools">
        <select
          aria-label="Enrollment status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          {[
            "active",
            "pending",
            "waitlisted",
            "completed",
            "withdrawn",
            "rejected",
          ].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
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
            render: (r) => `${(r.progress as { percent: number }).percent}%`,
          },
        ]}
        actions={(r) => (
          <>
            {["pending", "waitlisted", "rejected", "withdrawn"].includes(
              text(r, "status"),
            ) && (
              <ActionButton
                onClick={() =>
                  action.mutateAsync({
                    path: `/enrollments/${r.id}`,
                    method: "PATCH",
                    body: { status: "active" },
                  })
                }
              >
                Approve
              </ActionButton>
            )}
            {text(r, "status") !== "completed" && (
              <ActionButton
                onClick={async () => {
                  if (confirm("Withdraw this enrollment?"))
                    await action.mutateAsync({
                      path: `/enrollments/${r.id}`,
                      method: "PATCH",
                      body: { status: "withdrawn" },
                    });
                }}
              >
                Withdraw
              </ActionButton>
            )}
          </>
        )}
      />
      {modal && (
        <BulkEnrollment
          courses={courses.data?.items || []}
          users={users.data?.items || []}
          close={() => setModal(false)}
        />
      )}
    </>
  );
}
function BulkEnrollment({
  courses,
  users,
  close,
}: {
  courses: Course[];
  users: Entity[];
  close: () => void;
}) {
  const [selected, setSelected] = useState<string[]>([]),
    action = useAction();
  return (
    <Modal title="Enroll learners" onClose={close}>
      <DataForm
        fields={[
          {
            name: "course_id",
            label: "Published course",
            type: "select",
            required: true,
            options: courses.map((c) => ({ value: c.id, label: c.title })),
          },
        ]}
        label="Enroll selected learners"
        onSubmit={async (v) => {
          if (!selected.length) throw new Error("Select at least one learner");
          await action.mutateAsync({
            path: "/enrollments/bulk",
            body: { ...v, user_ids: selected },
          });
          close();
        }}
      >
        <fieldset className="question-checks wide">
          <legend>Learners</legend>
          {users
            .filter((u) => (u.roles as string[]).includes("student"))
            .map((u) => (
              <label key={u.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(u.id)}
                  onChange={(e) =>
                    setSelected(
                      e.target.checked
                        ? [...selected, u.id]
                        : selected.filter((id) => id !== u.id),
                    )
                  }
                />
                {text(u, "name")}
              </label>
            ))}
        </fieldset>
      </DataForm>
    </Modal>
  );
}

function CohortMembers({
  cohort,
  close,
}: {
  cohort: Entity;
  close: () => void;
}) {
  const [page, setPage] = useState(1),
    [search, setSearch] = useState("");
  const members = useApi<Page>(
    `/cohorts/${cohort.id}/members?page=${page}&search=${encodeURIComponent(search)}`,
  );
  const users = useApi<Page>("/users?role=student&page_size=100");
  const action = useAction();
  return (
    <Modal title={`Members · ${String(cohort.name)}`} onClose={close}>
      <DataForm
        fields={[
          {
            name: "user_id",
            label: "Student",
            type: "select",
            required: true,
            options: users.data?.items.map((u) => ({
              value: u.id,
              label: String(u.name),
            })),
          },
        ]}
        label="Add to cohort"
        onSubmit={async (v) => {
          await action.mutateAsync({
            path: `/cohorts/${cohort.id}/members/${v.user_id}`,
          });
        }}
      />
      <ErrorBox error={users.error} />
      <Table
        data={members.data}
        loading={members.isLoading}
        error={members.error}
        page={page}
        setPage={setPage}
        search={search}
        setSearch={setSearch}
        columns={[
          { key: "name", label: "Name" },
          { key: "email", label: "Email" },
        ]}
        actions={(u) => (
          <ActionButton
            onClick={async () => {
              if (confirm("Remove this student from the cohort?"))
                await action.mutateAsync({
                  path: `/cohorts/${cohort.id}/members/${u.id}`,
                  method: "DELETE",
                });
            }}
          >
            Remove
          </ActionButton>
        )}
      />
    </Modal>
  );
}
