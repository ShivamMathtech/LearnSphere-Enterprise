import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  BookOpen,
  ArrowRight,
  Plus,
  PlayCircle,
  CheckCircle2,
  Clock,
  Search,
  ArrowLeft,
  FileText,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
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
  ProgressBar,
  type Field,
} from "../components/UI";
import { api, download, send, upload } from "../services/api";
import type {
  Course,
  Entity,
  Enrollment,
  Lesson,
  Page,
  Section,
} from "../types/domain";
import { CourseAssessments } from "./Assessments";
import { CourseCommunity } from "./Community";
const option = (values: string[]) =>
  values.map((value) => ({ value, label: value.replaceAll("_", " ") }));
export const courseFields: Field[] = [
  { name: "title", label: "Course title", required: true },
  {
    name: "slug",
    label: "URL slug",
    required: true,
    help: "Lowercase words separated by hyphens.",
  },
  {
    name: "description",
    label: "Description",
    type: "textarea",
    required: true,
  },
  {
    name: "objectives",
    label: "Learning objectives",
    type: "textarea",
    required: true,
  },
  { name: "prerequisites", label: "Prerequisites", type: "textarea" },
  {
    name: "difficulty",
    label: "Difficulty",
    type: "select",
    options: option(["beginner", "intermediate", "advanced"]),
    default: "beginner",
  },
  {
    name: "enrollment_policy",
    label: "Enrollment policy",
    type: "select",
    options: option(["open", "approval", "closed"]),
    default: "open",
  },
  {
    name: "visibility",
    label: "Catalog visibility",
    type: "select",
    options: option(["institution", "assigned"]),
    default: "institution",
  },
  {
    name: "estimated_minutes",
    label: "Estimated minutes",
    type: "number",
    min: 1,
    default: 60,
  },
  {
    name: "max_learners",
    label: "Enrollment capacity",
    type: "number",
    min: 1,
    default: 100,
  },
  {
    name: "require_assessments",
    label: "Require passing assessments for completion",
    type: "checkbox",
    default: true,
  },
];
function CourseCover({ course, index }: { course: Course; index: number }) {
  const image = useQuery({
    queryKey: ["thumbnail", course.id, course.thumbnail_id],
    enabled: !!course.thumbnail_id,
    queryFn: async () =>
      (
        await api.get<Blob>(`/courses/${course.id}/thumbnail`, {
          responseType: "blob",
        })
      ).data,
    retry: 1,
  });
  const [url, setUrl] = useState("");
  useEffect(() => {
    if (!image.data) {
      setUrl("");
      return;
    }
    const next = URL.createObjectURL(image.data);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [image.data]);
  return (
    <div className={`course-cover cover-${index % 4}`}>
      {url ? (
        <img className="course-thumbnail" src={url} alt="" />
      ) : (
        <>
          <BookOpen size={65} strokeWidth={1.1} />
          <div className="cover-orbit" />
        </>
      )}
      <span>{course.difficulty.toUpperCase()}</span>
      {image.isError && (
        <small className="thumbnail-error">Thumbnail unavailable</small>
      )}
    </div>
  );
}
export function CourseCatalog() {
  const [search, setSearch] = useState(""),
    [status, setStatus] = useState(""),
    [page, setPage] = useState(1);
  const { can } = useAuth();
  const query = useApi<Page<Course>>(
    `/courses?search=${encodeURIComponent(search)}&status=${status}&page=${page}&page_size=9`,
  );
  return (
    <>
      <Heading
        eyebrow="EXPLORE & GROW"
        title="A world of learning"
        description="Discover courses designed to move you forward."
      >
        {can("courses.create") && (
          <Link className="button primary" to="/courses/new">
            <Plus size={17} /> Create course
          </Link>
        )}
      </Heading>
      <div className="catalog-tools">
        <label className="search-box">
          <Search size={18} />
          <input
            aria-label="Search courses"
            placeholder="Find your next course…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <select
          aria-label="Filter by publication status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          {["published", "draft", "in_review", "archived"].map((s) => (
            <option key={s} value={s}>
              {s.replace("_", " ")}
            </option>
          ))}
        </select>
        <span className="muted">{query.data?.total || 0} courses</span>
      </div>
      <ErrorBox error={query.error} />
      {query.isLoading ? (
        <Loading />
      ) : (
        <div className="course-grid">
          {query.data?.items.map((c, i) => (
            <Link to={`/courses/${c.id}`} className="course-card" key={c.id}>
              <CourseCover course={c} index={i} />
              <div className="course-card-body">
                <Badge>{c.status}</Badge>
                <h3>{c.title}</h3>
                <p className="line-clamp">{c.description}</p>
                <div className="course-meta">
                  <span>
                    <Clock size={14} /> {c.estimated_minutes} min
                  </span>
                  <span>
                    View course <ArrowRight size={15} />
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
      {query.data?.total === 0 && <Empty>No courses match your search.</Empty>}
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
            disabled={!query.data || page * 9 >= query.data.total}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </>
  );
}
export function CourseEditor() {
  const { id } = useParams(),
    navigate = useNavigate();
  const query = useApi<Course>(`/courses/${id}`, !!id);
  const client = useQueryClient();
  const options = useApi<{ categories: Entity[]; departments: Entity[] }>(
    "/courses/authoring-options",
  );
  const fields: Field[] = [
    ...courseFields,
    { name: "tags", label: "Tags (comma separated)" },
    {
      name: "category_id",
      label: "Category",
      type: "select",
      options: options.data?.categories.map((r) => ({
        value: r.id,
        label: String(r.name),
      })),
    },
    {
      name: "department_id",
      label: "Department",
      type: "select",
      options: options.data?.departments.map((r) => ({
        value: r.id,
        label: String(r.name),
      })),
    },
  ];
  return (
    <>
      <Heading
        title={id ? "Edit course" : "Create something worth learning"}
        description="Start with the essentials, then build your curriculum."
      />
      {id && query.isLoading ? (
        <Loading />
      ) : (
        <div className="panel form-panel">
          <DataForm
            fields={fields}
            initial={
              query.data
                ? {
                    ...query.data,
                    tags: ((query.data.tags as string[]) || []).join(", "),
                  }
                : {}
            }
            label={id ? "Save course" : "Create draft"}
            onSubmit={async (values) => {
              const course = await send<Course>(
                id ? `/courses/${id}` : "/courses",
                {
                  ...values,
                  tags: String(values.tags || "")
                    .split(",")
                    .map((x) => x.trim())
                    .filter(Boolean),
                },
                id ? "PUT" : "POST",
              );
              await client.invalidateQueries();
              navigate(`/courses/${course.id}`);
            }}
          />
        </div>
      )}
      <ErrorBox error={query.error || options.error} />
      {id &&
        query.data &&
        ["draft", "in_review"].includes(query.data.status) && (
          <section className="panel info-panel">
            <h2>Course thumbnail</h2>
            <p>
              Upload a PNG or JPEG. The catalog uses this image after you save
              it.
            </p>
            <FileUploader
              courseId={id}
              purpose="resource"
              onUploaded={async (fileId) => {
                await send(
                  `/courses/${id}/thumbnail`,
                  { file_id: fileId },
                  "PUT",
                );
                await client.invalidateQueries();
              }}
            />
            {!!query.data.thumbnail_id && (
              <ActionButton
                onClick={async () => {
                  await send(
                    `/courses/${id}/thumbnail`,
                    { file_id: null },
                    "PUT",
                  );
                  await client.invalidateQueries();
                }}
              >
                Remove thumbnail
              </ActionButton>
            )}
          </section>
        )}
    </>
  );
}
export function CourseDetail() {
  const { id } = useParams();
  const query = useApi<Course>(`/courses/${id}`),
    action = useAction();
  const { can } = useAuth();
  const [tab, setTab] = useState("curriculum"),
    [modal, setModal] = useState(""),
    [editSection, setEditSection] = useState<Section | null>(null);
  const navigate = useNavigate();
  if (query.isLoading) return <Loading />;
  if (!query.data) return <ErrorBox error={query.error} />;
  const c = query.data,
    author = c.can_author,
    editable = ["draft", "in_review"].includes(c.status);
  const change = async (path: string, body?: unknown) => {
    await action.mutateAsync({ path, body });
    setModal("");
  };
  const lessonFields: Field[] = [
    { name: "title", label: "Lesson title", required: true },
    {
      name: "section_id",
      label: "Section",
      type: "select",
      required: true,
      options: c.sections?.map((s) => ({ value: s.id, label: s.title })),
    },
    {
      name: "kind",
      label: "Lesson type",
      type: "select",
      options: option(["text", "video", "pdf", "document", "link", "resource"]),
      default: "text",
    },
    {
      name: "position",
      label: "Order within section (0-based)",
      type: "number",
      default: 0,
    },
    { name: "content", label: "Lesson content", type: "textarea" },
    {
      name: "url",
      label: "Video or resource URL",
      help: "Use a direct HTTP(S) video URL for playback.",
    },
    {
      name: "duration_minutes",
      label: "Duration in minutes",
      type: "number",
      min: 1,
      default: 10,
    },
    {
      name: "prerequisite_id",
      label: "Prerequisite lesson",
      type: "select",
      options: c.sections?.flatMap((s) =>
        s.lessons.map((l) => ({ value: l.id, label: l.title })),
      ),
    },
    {
      name: "drip_days",
      label: "Days after enrollment to unlock",
      type: "number",
      default: 0,
    },
  ];
  return (
    <>
      <Link className="text-link back-link" to="/courses">
        <ArrowLeft size={16} /> Course catalog
      </Link>
      <div className="course-hero">
        <div>
          <Badge>{c.status}</Badge>
          <h1>{c.title}</h1>
          <p>{c.description}</p>
          <div className="course-hero-meta">
            <span>
              <Clock size={16} /> {c.estimated_minutes} minutes
            </span>
            <span>
              <BookOpen size={16} />{" "}
              {c.sections?.reduce((n, s) => n + s.lessons.length, 0)} lessons
            </span>
            <span>Revision {c.version}</span>
          </div>
        </div>
        <div className="course-hero-action">
          {c.enrollment && (
            <>
              <Badge>{c.enrollment.status}</Badge>
              <ProgressBar value={c.progress?.percent || 0} />
              <p>{c.progress?.percent || 0}% complete</p>
              {["active", "completed"].includes(c.enrollment.status) && (
                <Link className="button primary" to={`/learn/${c.id}`}>
                  <PlayCircle size={17} /> Continue learning
                </Link>
              )}
            </>
          )}
          {!c.enrollment && can("progress.update") && (
            <ActionButton
              className="button primary"
              onClick={() =>
                action.mutateAsync({
                  path: "/enrollments",
                  body: { course_id: c.id },
                })
              }
            >
              Enroll in course <ArrowRight size={17} />
            </ActionButton>
          )}
          {author && (
            <>
              {editable && (
                <Link className="button" to={`/courses/${c.id}/edit`}>
                  Edit course details
                </Link>
              )}
              {c.status === "draft" && (
                <ActionButton onClick={() => change(`/courses/${c.id}/review`)}>
                  Submit for review
                </ActionButton>
              )}
              {c.status === "in_review" && (
                <ActionButton
                  className="button primary"
                  onClick={() => change(`/courses/${c.id}/publish`)}
                >
                  Publish course
                </ActionButton>
              )}
              {!editable && (
                <ActionButton
                  onClick={async () => {
                    const next = await send<Course>(
                      `/courses/${c.id}/revision`,
                    );
                    navigate(`/courses/${next.id}`);
                  }}
                >
                  Create new revision
                </ActionButton>
              )}
              {c.status === "published" && (
                <ActionButton
                  onClick={async () => {
                    if (
                      confirm(
                        "Archive this course? New enrollments will stop. Existing learning records remain available.",
                      )
                    )
                      await change(`/courses/${c.id}/archive`);
                  }}
                >
                  Archive
                </ActionButton>
              )}
            </>
          )}
        </div>
      </div>
      <div className="tabs" role="tablist" aria-label="Course sections">
        {["curriculum", "assessments", "community", "details"].map((t) => (
          <button
            role="tab"
            aria-selected={tab === t}
            className={tab === t ? "selected" : ""}
            key={t}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "curriculum" && (
        <div className="content-columns">
          <div>
            {author && editable && (
              <div className="actions section-actions">
                <button className="button" onClick={() => setModal("section")}>
                  <Plus size={16} /> Section
                </button>
                <button
                  className="button primary"
                  onClick={() => setModal("lesson")}
                >
                  <Plus size={16} /> Lesson
                </button>
              </div>
            )}
            {c.sections?.map((section) => (
              <section className="panel curriculum-section" key={section.id}>
                <div className="section-heading">
                  <h2>{section.title}</h2>
                  <div className="actions">
                    <span className="muted">
                      {section.lessons.length} lessons
                    </span>
                    {author && editable && (
                      <>
                        <button
                          className="button small"
                          onClick={() => setEditSection(section)}
                        >
                          Edit section
                        </button>
                        <ActionButton
                          onClick={async () => {
                            if (confirm("Delete this empty section?"))
                              await action.mutateAsync({
                                path: `/sections/${section.id}`,
                                method: "DELETE",
                              });
                          }}
                        >
                          Delete section
                        </ActionButton>
                      </>
                    )}
                  </div>
                </div>
                {section.lessons.map((lesson) => (
                  <div className="lesson-row" key={lesson.id}>
                    <FileText size={18} />
                    <div>
                      <strong>{lesson.title}</strong>
                      <small>
                        {lesson.kind} · {lesson.duration_minutes} min
                        {lesson.drip_days > 0 &&
                          ` · unlocks day ${lesson.drip_days}`}
                      </small>
                    </div>
                    <div className="actions">
                      {author && editable && (
                        <>
                          <button
                            className="button small"
                            onClick={() => setModal(lesson.id)}
                          >
                            Edit
                          </button>
                          <ActionButton
                            onClick={async () => {
                              if (confirm("Delete this draft lesson?"))
                                await action.mutateAsync({
                                  path: `/lessons/${lesson.id}`,
                                  method: "DELETE",
                                });
                            }}
                          >
                            Delete
                          </ActionButton>
                        </>
                      )}
                      {c.progress?.completed_lesson_ids.includes(lesson.id) && (
                        <CheckCircle2 size={19} className="teal" />
                      )}
                    </div>
                    {modal === lesson.id && (
                      <Modal title="Edit lesson" onClose={() => setModal("")}>
                        <DataForm
                          fields={lessonFields}
                          initial={lesson}
                          onSubmit={async (values) => {
                            await action.mutateAsync({
                              path: `/lessons/${lesson.id}`,
                              body: values,
                              method: "PUT",
                            });
                            setModal("");
                          }}
                        />
                        <FileUploader courseId={c.id} lessonId={lesson.id} />
                      </Modal>
                    )}
                  </div>
                ))}
              </section>
            ))}
            {!c.sections?.length && (
              <div className="panel">
                <Empty>Add a section to start building your curriculum.</Empty>
              </div>
            )}
          </div>
          <aside className="panel info-panel">
            <h2>What you’ll learn</h2>
            <p className="prose">
              {c.objectives ||
                "Learning objectives will be added before publication."}
            </p>
            <hr />
            <h3>Your instructors</h3>
            {c.instructors?.map((i) => (
              <p key={String(i.user_id)}>{i.name}</p>
            ))}
            {author && can("courses.assign_assistant") && (
              <button className="button" onClick={() => setModal("staff")}>
                Assign course staff
              </button>
            )}
            <hr />
            <h3>Before you begin</h3>
            <p className="muted prose">
              {c.prerequisites || "No prerequisites specified."}
            </p>
          </aside>
        </div>
      )}
      {tab === "assessments" && (
        <CourseAssessments courseId={c.id} canAuthor={!!author && editable} />
      )}
      {tab === "community" && <CourseCommunity courseId={c.id} />}
      {tab === "details" && (
        <section className="panel info-panel">
          <h2>Course information</h2>
          <p>
            Enrollment: {c.enrollment_policy} · Capacity: {c.max_learners} ·{" "}
            {c.difficulty}
          </p>
          <p>
            Completion requires all lessons
            {c.require_assessments ? " and passing required assessments." : "."}
          </p>
          {c.progress?.remaining.map((r) => (
            <p key={r}>• {r}</p>
          ))}
        </section>
      )}
      {editSection && (
        <Modal title="Edit section" onClose={() => setEditSection(null)}>
          <DataForm
            fields={[
              { name: "title", label: "Section title", required: true },
              { name: "position", label: "Order", type: "number" },
            ]}
            initial={editSection}
            onSubmit={async (body) => {
              await action.mutateAsync({
                path: `/sections/${editSection.id}`,
                method: "PUT",
                body,
              });
              setEditSection(null);
            }}
          />
        </Modal>
      )}
      {modal === "section" && (
        <Modal title="New section" onClose={() => setModal("")}>
          <DataForm
            fields={[
              { name: "title", label: "Section title", required: true },
              {
                name: "position",
                label: "Order",
                type: "number",
                default: c.sections?.length || 0,
              },
            ]}
            onSubmit={(values) => change(`/courses/${c.id}/sections`, values)}
          />
        </Modal>
      )}
      {modal === "lesson" && (
        <Modal title="New lesson" onClose={() => setModal("")}>
          <DataForm
            fields={lessonFields}
            onSubmit={(values) => change(`/courses/${c.id}/lessons`, values)}
          />
        </Modal>
      )}
      {modal === "staff" && (
        <StaffForm courseId={c.id} onClose={() => setModal("")} />
      )}
    </>
  );
}
function StaffForm({
  courseId,
  onClose,
}: {
  courseId: string;
  onClose: () => void;
}) {
  const query = useApi<Page<Entity>>(`/courses/${courseId}/staff-candidates`),
    action = useAction();
  return (
    <Modal title="Assign instructor or assistant" onClose={onClose}>
      <ErrorBox error={query.error} />
      <DataForm
        fields={[
          {
            name: "user_id",
            label: "Course staff member",
            type: "select",
            required: true,
            options: query.data?.items.map((u) => ({
              value: u.id,
              label: String(u.name),
            })),
          },
          { name: "can_grade", label: "Delegate grading", type: "checkbox" },
          {
            name: "can_discuss",
            label: "Delegate discussions",
            type: "checkbox",
            default: true,
          },
        ]}
        onSubmit={async (values) => {
          await action.mutateAsync({
            path: `/courses/${courseId}/instructors`,
            body: values,
          });
          onClose();
        }}
      />
    </Modal>
  );
}
export function FileUploader({
  courseId,
  lessonId,
  purpose = "resource",
  onUploaded,
}: {
  courseId: string;
  lessonId?: string;
  purpose?: "resource" | "submission";
  onUploaded?: (id: string) => void | Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null),
    [message, setMessage] = useState("");
  const queryClient = useQueryClient();
  return (
    <div className="upload-box">
      <label>
        Upload{" "}
        {purpose === "submission" ? "submission file" : "lesson resource"}
        <input
          type="file"
          accept=".pdf,.txt,.csv,.png,.jpg,.jpeg,.mp4,.docx,.pptx,.xlsx"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
      </label>
      <ActionButton
        onClick={async () => {
          if (!file) throw new Error("Choose a file first");
          const result = await upload(courseId, file, purpose);
          if (lessonId) await send(`/files/${result.id}/lessons/${lessonId}`);
          await onUploaded?.(result.id);
          setMessage(`${result.name} uploaded`);
          await queryClient.invalidateQueries();
        }}
      >
        Upload file
      </ActionButton>
      {message && (
        <small role="status" className="teal">
          {message}
        </small>
      )}
    </div>
  );
}
export function LearningPage() {
  const query = useApi<Page<Enrollment>>("/enrollments?page_size=100");
  return (
    <>
      <Heading
        title="Your learning journey"
        description="Pick up where you left off, and keep moving forward."
      />
      <ErrorBox error={query.error} />
      {query.isLoading ? (
        <Loading />
      ) : (
        <div className="learning-list">
          {query.data?.items.map((e) => (
            <div className="panel learning-card" key={e.id}>
              <span className="learning-icon">
                <GraduationIcon />
              </span>
              <div>
                <Badge>{e.status}</Badge>
                <h2>{e.course_title}</h2>
                <ProgressBar value={e.progress?.percent || 0} />
                <small>{e.progress?.percent || 0}% complete</small>
              </div>
              <Link className="button primary" to={`/learn/${e.course_id}`}>
                Continue <ArrowRight size={17} />
              </Link>
            </div>
          ))}
        </div>
      )}
      {query.data?.total === 0 && (
        <Empty>Find a course in the catalog to begin.</Empty>
      )}
    </>
  );
}
function GraduationIcon() {
  return <BookOpen size={32} />;
}
export function LearningPlayer() {
  const { id } = useParams(),
    course = useApi<Course>(`/courses/${id}`),
    [selected, setSelected] = useState(""),
    action = useAction();
  const lessonId =
    selected ||
    course.data?.progress?.last_lesson_id ||
    course.data?.sections?.[0]?.lessons[0]?.id;
  const lesson = useApi<Lesson>(`/lessons/${lessonId}`, !!lessonId);
  return (
    <>
      <Link to={`/courses/${id}`} className="text-link back-link">
        <ArrowLeft size={16} /> Back to course
      </Link>
      <Heading
        eyebrow="LEARNING PLAYER"
        title={course.data?.title || "Your classroom"}
      />
      <ErrorBox error={course.error} />
      <div className="player-layout">
        <aside className="panel player-sidebar">
          <ProgressBar value={course.data?.progress?.percent || 0} />
          <p>{course.data?.progress?.percent || 0}% complete</p>
          {course.data?.sections?.map((s) => (
            <div key={s.id}>
              <h3>{s.title}</h3>
              {s.lessons.map((l) => (
                <button
                  key={l.id}
                  className={
                    lessonId === l.id
                      ? "player-lesson selected"
                      : "player-lesson"
                  }
                  onClick={() => setSelected(l.id)}
                >
                  {course.data?.progress?.completed_lesson_ids.includes(
                    l.id,
                  ) ? (
                    <CheckCircle2 size={16} />
                  ) : (
                    <PlayCircle size={16} />
                  )}
                  <span>{l.title}</span>
                </button>
              ))}
            </div>
          ))}
        </aside>
        <section className="panel lesson-content">
          <ErrorBox error={lesson.error} />
          {lesson.isLoading && <Loading />}
          {lesson.data && (
            <>
              <Badge>{lesson.data.kind}</Badge>
              <h2>{lesson.data.title}</h2>
              {lesson.data.kind === "video" && lesson.data.url && (
                <video
                  src={lesson.data.url}
                  controls
                  preload="metadata"
                  aria-label={lesson.data.title}
                />
              )}
              <div className="prose">{lesson.data.content}</div>
              {lesson.data.url && (
                <a
                  className="text-link"
                  href={lesson.data.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open linked resource <ArrowRight size={15} />
                </a>
              )}
              {lesson.data.file_ids?.map((fid, index) => (
                <ActionButton
                  key={fid}
                  onClick={() =>
                    download(`/files/${fid}/download`, `resource-${index + 1}`)
                  }
                >
                  Download resource {index + 1}
                </ActionButton>
              ))}
              <div className="lesson-footer">
                <ActionButton
                  className="button primary"
                  onClick={() =>
                    action.mutateAsync({
                      path: `/progress/${lesson.data?.id}/complete`,
                    })
                  }
                >
                  <CheckCircle2 size={17} /> Mark lesson complete
                </ActionButton>
                <Link to={`/courses/${id}`} className="button">
                  Assessments & discussions
                </Link>
              </div>
            </>
          )}
          {course.data?.progress?.eligible && course.data.enrollment && (
            <div className="success-box">
              <p>You have met the completion requirements.</p>
              <ActionButton
                onClick={() =>
                  action.mutateAsync({
                    path: `/certificates/issue/${course.data?.enrollment?.id}`,
                  })
                }
              >
                Issue my certificate
              </ActionButton>
              <Link to="/certificates" className="text-link">
                View certificates
              </Link>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
