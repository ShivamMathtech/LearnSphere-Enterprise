import { useState } from "react";
import { MessageSquare, Megaphone, Bell, CalendarDays } from "lucide-react";
import { useAuth } from "../app/Auth";
import { useApi, useAction } from "../hooks/api";
import {
  ActionButton,
  Badge,
  DataForm,
  Empty,
  ErrorBox,
  Heading,
  Modal,
  Table,
  date,
  text,
  type Field,
} from "../components/UI";
import type { Course, Entity, Page } from "../types/domain";
import { CoursePicker } from "./Assessments";
export function CommunityPage() {
  const [course, setCourse] = useState("");
  return (
    <>
      <Heading
        title="A connected classroom"
        description="Ask questions, share ideas and stay in the conversation."
      />
      <CoursePicker value={course} onChange={setCourse} />
      {course ? (
        <CourseCommunity courseId={course} />
      ) : (
        <div className="panel">
          <Empty>Choose a course to join its community.</Empty>
        </div>
      )}
    </>
  );
}
export function CourseCommunity({ courseId }: { courseId: string }) {
  const [kind, setKind] = useState<"discussions" | "announcements">(
      "discussions",
    ),
    [page, setPage] = useState(1),
    [modal, setModal] = useState(false),
    [thread, setThread] = useState<Entity | null>(null),
    [message, setMessage] = useState(false);
  const { can } = useAuth(),
    query = useApi<Page>(`/${kind}?course_id=${courseId}&page=${page}`),
    action = useAction(),
    enrollments = useApi<Page>(
      `/enrollments?course_id=${courseId}&page_size=100`,
      can("messages.create"),
    );
  return (
    <>
      <div className="section-heading">
        <div className="tabs">
          <button
            className={kind === "discussions" ? "selected" : ""}
            onClick={() => {
              setKind("discussions");
              setPage(1);
            }}
          >
            <MessageSquare size={16} /> Discussions
          </button>
          <button
            className={kind === "announcements" ? "selected" : ""}
            onClick={() => {
              setKind("announcements");
              setPage(1);
            }}
          >
            <Megaphone size={16} /> Announcements
          </button>
        </div>
        <div className="actions">
          {can(
            kind === "discussions"
              ? "discussions.write"
              : "announcements.create",
          ) && (
            <button className="button primary" onClick={() => setModal(true)}>
              New {kind === "discussions" ? "discussion" : "announcement"}
            </button>
          )}
          {can("messages.create") && (
            <button className="button" onClick={() => setMessage(true)}>
              Message learner
            </button>
          )}
        </div>
      </div>
      <ErrorBox error={query.error} />
      {query.data?.items.map((row) => (
        <article className="panel post" key={row.id}>
          <div className="post-author">
            <span className="avatar">
              {text(row, "author_name").slice(0, 1)}
            </span>
            <div>
              <strong>{text(row, "author_name")}</strong>
              <small>{date(row.created_at)}</small>
            </div>
            <Badge>
              {kind === "discussions" ? "Discussion" : "Announcement"}
            </Badge>
          </div>
          <h2>{text(row, "title")}</h2>
          <p className="prose">{text(row, "body")}</p>
          {kind === "discussions" && (
            <button className="button small" onClick={() => setThread(row)}>
              Open conversation
            </button>
          )}
        </article>
      ))}
      {query.data?.total === 0 && (
        <div className="panel">
          <Empty>Be the first to start a conversation.</Empty>
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
      {modal && (
        <Modal
          title={`New ${kind === "discussions" ? "discussion" : "announcement"}`}
          onClose={() => setModal(false)}
        >
          <DataForm
            fields={[
              { name: "title", label: "Title", required: true },
              {
                name: "body",
                label: "Message",
                type: "textarea",
                required: true,
              },
            ]}
            label="Publish"
            onSubmit={async (v) => {
              await action.mutateAsync({
                path: `/${kind}`,
                body: { ...v, course_id: courseId },
              });
              setModal(false);
            }}
          />
        </Modal>
      )}
      {thread && <Thread thread={thread} close={() => setThread(null)} />}{" "}
      {message && (
        <Modal
          title="Message an enrolled learner"
          onClose={() => setMessage(false)}
        >
          <DataForm
            fields={[
              {
                name: "recipient_id",
                label: "Learner",
                type: "select",
                required: true,
                options: enrollments.data?.items.map((e) => ({
                  value: text(e, "user_id"),
                  label: text(e, "student_name"),
                })),
              },
              {
                name: "body",
                label: "Message",
                type: "textarea",
                required: true,
              },
            ]}
            label="Send message"
            onSubmit={async (v) => {
              await action.mutateAsync({
                path: "/messages",
                body: { ...v, course_id: courseId },
              });
              setMessage(false);
            }}
          />
        </Modal>
      )}
    </>
  );
}
function Thread({ thread, close }: { thread: Entity; close: () => void }) {
  const [page, setPage] = useState(1),
    query = useApi<Page>(`/discussions/${thread.id}/replies?page=${page}`),
    action = useAction();
  return (
    <Modal title={text(thread, "title")} onClose={close}>
      <p className="prose">{text(thread, "body")}</p>
      <ErrorBox error={query.error} />
      {query.data?.items.map((r) => (
        <div className="reply" key={r.id}>
          <strong>{text(r, "author_name")}</strong>
          <small>{date(r.created_at)}</small>
          <p className="prose">{text(r, "body")}</p>
        </div>
      ))}
      <div className="actions">
        <button
          className="button small"
          disabled={page === 1}
          onClick={() => setPage(page - 1)}
        >
          Previous
        </button>
        <button
          className="button small"
          disabled={!query.data || page * 20 >= query.data.total}
          onClick={() => setPage(page + 1)}
        >
          Next
        </button>
      </div>
      <DataForm
        fields={[
          {
            name: "body",
            label: "Your reply",
            type: "textarea",
            required: true,
          },
        ]}
        label="Post reply"
        onSubmit={(v) =>
          action.mutateAsync({
            path: `/discussions/${thread.id}/replies`,
            body: v,
          })
        }
      />
    </Modal>
  );
}
export function NotificationsPage() {
  const [page, setPage] = useState(1),
    [unread, setUnread] = useState(false),
    query = useApi<Page>(`/notifications?page=${page}&unread=${unread}`),
    action = useAction();
  return (
    <>
      <Heading
        title="Your notifications"
        description="The updates that keep your learning on track."
      >
        <label className="check-label">
          <input
            type="checkbox"
            checked={unread}
            onChange={(e) => {
              setUnread(e.target.checked);
              setPage(1);
            }}
          />
          Unread only
        </label>
      </Heading>
      <ErrorBox error={query.error} />
      <div className="panel notification-list">
        {query.data?.items.map((n) => (
          <div
            className={n.read_at ? "notification read" : "notification"}
            key={n.id}
          >
            <span className="notification-symbol">
              <Bell size={20} />
            </span>
            <div>
              <h3>{text(n, "title")}</h3>
              <p className="prose">{text(n, "body")}</p>
              <small>{date(n.created_at)}</small>
            </div>
            {!n.read_at && (
              <ActionButton
                onClick={() =>
                  action.mutateAsync({ path: `/notifications/${n.id}/read` })
                }
              >
                Mark read
              </ActionButton>
            )}
          </div>
        ))}
        {query.data?.total === 0 && <Empty>You’re all caught up.</Empty>}
      </div>
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
    </>
  );
}
export function AttendancePage() {
  const [course, setCourse] = useState(""),
    [page, setPage] = useState(1),
    [create, setCreate] = useState(false),
    [selected, setSelected] = useState<Entity | null>(null);
  const query = useApi<Page>(
      `/attendance?page=${page}${course ? "&course_id=" + course : ""}`,
    ),
    detail = useApi<Course>(`/courses/${course}`, !!course),
    action = useAction(),
    { can } = useAuth();
  const fields: Field[] = [
    { name: "title", label: "Session title", required: true },
    {
      name: "starts_at",
      label: "Starts at",
      type: "datetime-local",
      required: true,
    },
    {
      name: "ends_at",
      label: "Ends at",
      type: "datetime-local",
      required: true,
    },
    {
      name: "instructor_id",
      label: "Assigned instructor",
      type: "select",
      required: true,
      options: detail.data?.instructors?.map((u) => ({
        value: String(u.user_id),
        label: u.name,
      })),
    },
    {
      name: "meeting_url",
      label: "Meeting link (HTTPS)",
      help: "Manual meeting link. No provider integration is configured.",
    },
  ];
  return (
    <>
      <Heading
        title="Live learning & attendance"
        description="Bring the classroom together, wherever learning happens."
      >
        {can("attendance.manage") && (
          <button
            className="button primary"
            disabled={!course}
            onClick={() => setCreate(true)}
          >
            <CalendarDays size={16} /> Schedule session
          </button>
        )}
      </Heading>
      <CoursePicker value={course} onChange={setCourse} />
      <Table
        data={query.data}
        loading={query.isLoading}
        error={query.error}
        page={page}
        setPage={setPage}
        columns={[
          { key: "title", label: "Session" },
          {
            key: "starts_at",
            label: "Starts",
            render: (r) => date(r.starts_at),
          },
          { key: "ends_at", label: "Ends", render: (r) => date(r.ends_at) },
        ]}
        actions={(r) => (
          <>
            <button className="button small" onClick={() => setSelected(r)}>
              Attendance
            </button>
            {r.meeting_url ? (
              <a
                className="button small"
                href={text(r, "meeting_url")}
                target="_blank"
                rel="noopener noreferrer"
              >
                Join meeting
              </a>
            ) : (
              <Badge>Manual session</Badge>
            )}
          </>
        )}
      />
      {create && (
        <Modal title="Schedule live session" onClose={() => setCreate(false)}>
          <DataForm
            fields={fields}
            onSubmit={async (v) => {
              await action.mutateAsync({
                path: "/attendance",
                body: {
                  ...v,
                  course_id: course,
                  meeting_url: v.meeting_url || null,
                },
              });
              setCreate(false);
            }}
          />
        </Modal>
      )}
      {selected && (
        <AttendanceRecords session={selected} close={() => setSelected(null)} />
      )}
    </>
  );
}
function AttendanceRecords({
  session,
  close,
}: {
  session: Entity;
  close: () => void;
}) {
  const [page, setPage] = useState(1),
    [csv, setCsv] = useState(false),
    query = useApi<Page>(`/attendance/${session.id}/records?page=${page}`),
    roster = useApi<Page>(
      `/enrollments?course_id=${text(session, "course_id")}&page_size=100`,
    ),
    action = useAction(),
    { can } = useAuth();
  return (
    <Modal title={`Attendance: ${text(session, "title")}`} onClose={close}>
      <Table
        data={query.data}
        loading={query.isLoading}
        error={query.error}
        page={page}
        setPage={setPage}
        columns={[
          { key: "student_name", label: "Learner" },
          {
            key: "status",
            label: "Status",
            render: (r) => <Badge>{text(r, "status")}</Badge>,
          },
          { key: "note", label: "Note" },
        ]}
      />
      {can("attendance.manage") && (
        <>
          <h3>Record or correct attendance</h3>
          <DataForm
            fields={[
              {
                name: "user_id",
                label: "Learner",
                type: "select",
                required: true,
                options: roster.data?.items.map((e) => ({
                  value: text(e, "user_id"),
                  label: text(e, "student_name"),
                })),
              },
              {
                name: "status",
                label: "Attendance",
                type: "select",
                required: true,
                options: ["present", "absent", "late", "excused"].map(
                  (value) => ({ value, label: value }),
                ),
              },
              { name: "note", label: "Correction note" },
            ]}
            onSubmit={(v) =>
              action.mutateAsync({
                path: `/attendance/${session.id}/records`,
                body: v,
                method: "PUT",
              })
            }
          />
          <button className="button" onClick={() => setCsv(!csv)}>
            Import attendance CSV
          </button>
          {csv && (
            <DataForm
              fields={[
                {
                  name: "csv_text",
                  label: "CSV: user_id,status,note",
                  type: "textarea",
                  required: true,
                },
              ]}
              label="Import attendance"
              onSubmit={(v) =>
                action.mutateAsync({
                  path: `/attendance/${session.id}/import`,
                  body: { ...v, mapping: {}, role: "student" },
                })
              }
            />
          )}
        </>
      )}
    </Modal>
  );
}
