import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  ClipboardCheck,
  Timer,
  CheckCircle2,
  ArrowLeft,
} from "lucide-react";
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
  date,
  type Field,
} from "../components/UI";
import { download, send } from "../services/api";
import type {
  Answer,
  Assignment,
  Attempt,
  Course,
  Entity,
  Page,
  Question,
  Submission,
} from "../types/domain";
import { FileUploader } from "./Courses";
export function CoursePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (id: string) => void;
}) {
  const courses = useApi<Page<Course>>("/courses?page_size=100");
  return (
    <label className="course-picker">
      Course
      <select
        aria-label="Select course"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Choose a course…</option>
        {courses.data?.items.map((c) => (
          <option value={c.id} key={c.id}>
            {c.title}
          </option>
        ))}
      </select>
      <ErrorBox error={courses.error} />
    </label>
  );
}
export function AssessmentsPage() {
  const [course, setCourse] = useState("");
  const query = useApi<Course>(`/courses/${course}`, !!course);
  return (
    <>
      <Heading
        title="Assessments & feedback"
        description="Turn understanding into practice, and feedback into progress."
      />
      <CoursePicker value={course} onChange={setCourse} />
      {course ? (
        <CourseAssessments
          courseId={course}
          canAuthor={
            !!query.data?.can_author &&
            ["draft", "in_review"].includes(query.data.status)
          }
        />
      ) : (
        <div className="panel">
          <Empty>Select a course to view its quizzes and assignments.</Empty>
        </div>
      )}
    </>
  );
}
export function CourseAssessments({
  courseId,
  canAuthor,
}: {
  courseId: string;
  canAuthor: boolean;
}) {
  const { can } = useAuth(),
    [modal, setModal] = useState(""),
    navigate = useNavigate();
  const quizzes = useApi<Page<Entity>>(
      `/quizzes?course_id=${courseId}&page_size=100`,
    ),
    assignments = useApi<Page<Assignment>>(
      `/assignments?course_id=${courseId}&page_size=100`,
    ),
    attempts = useApi<Page<Attempt>>(
      `/attempts?course_id=${courseId}&page_size=100`,
    ),
    submissions = useApi<Page<Submission>>(
      `/submissions?course_id=${courseId}&page_size=100`,
    );
  const [submitAssignment, setSubmitAssignment] = useState<Assignment | null>(
      null,
    ),
    [grade, setGrade] = useState<Submission | null>(null);
  const action = useAction();
  const [editing, setEditing] = useState<{
    kind: string;
    value: Entity;
  } | null>(null);
  const bank = useApi<Page<Question>>(
    `/questions?course_id=${courseId}&page_size=100`,
    canAuthor,
  );
  const remove = async (kind: string, id: string) => {
    if (confirm("Delete this draft item? This cannot be undone."))
      await action.mutateAsync({ path: `/${kind}/${id}`, method: "DELETE" });
  };
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>Practice. Assess. Improve.</h2>
          <p>Quizzes, assignments and meaningful feedback.</p>
        </div>
        {canAuthor && (
          <div className="actions">
            <button className="button" onClick={() => setModal("question")}>
              Add question
            </button>
            <button className="button" onClick={() => setModal("quiz")}>
              <Plus size={16} /> Quiz
            </button>
            <button
              className="button primary"
              onClick={() => setModal("assignment")}
            >
              <Plus size={16} /> Assignment
            </button>
          </div>
        )}
      </div>
      <ErrorBox error={quizzes.error || assignments.error} />
      <div className="assessment-grid">
        <section className="panel info-panel">
          <h2>
            <ClipboardCheck size={20} /> Quizzes
          </h2>
          {quizzes.isLoading ? (
            <Loading />
          ) : (
            quizzes.data?.items.map((q) => (
              <div className="assessment-row" key={q.id}>
                <div>
                  <h3>{String(q.title)}</h3>
                  <p>
                    {String(q.time_limit_minutes)} min ·{" "}
                    {String(q.attempt_limit)} attempts · Pass{" "}
                    {String(q.pass_percent)}%
                  </p>
                  <small>
                    Release: {String(q.release_policy).replaceAll("_", " ")}
                  </small>
                </div>
                <div className="actions">
                  {canAuthor && (
                    <>
                      <ActionButton
                        onClick={async () =>
                          setEditing({
                            kind: "quiz",
                            value: await send<Entity>(
                              `/quizzes/${q.id}/author`,
                              undefined,
                              "GET",
                            ),
                          })
                        }
                      >
                        Edit quiz
                      </ActionButton>
                      <ActionButton onClick={() => remove("quizzes", q.id)}>
                        Delete quiz
                      </ActionButton>
                    </>
                  )}
                  {can("assessments.attempt") && (
                    <ActionButton
                      onClick={async () => {
                        const a = await send<Attempt>(`/quizzes/${q.id}/start`);
                        navigate(`/attempts/${a.id}`);
                      }}
                    >
                      Start / resume
                    </ActionButton>
                  )}
                  {can("assessments.grade") && (
                    <ActionButton
                      onClick={() =>
                        action.mutateAsync({ path: `/quizzes/${q.id}/release` })
                      }
                    >
                      Release results
                    </ActionButton>
                  )}
                </div>
              </div>
            ))
          )}
          {quizzes.data?.total === 0 && (
            <Empty>No quizzes in this course yet.</Empty>
          )}
        </section>
        <section className="panel info-panel">
          <h2>Assignments</h2>
          {assignments.data?.items.map((a) => (
            <div className="assessment-row" key={a.id}>
              <div>
                <h3>{a.title}</h3>
                <p className="prose">{a.instructions}</p>
                <small>
                  Due: {date(a.due_at)} · {a.max_marks} marks
                </small>
                {a.file_ids.map((fid, i) => (
                  <ActionButton
                    key={fid}
                    onClick={() =>
                      download(
                        `/files/${fid}/download`,
                        `assignment-resource-${i + 1}`,
                      )
                    }
                  >
                    Resource {i + 1}
                  </ActionButton>
                ))}
              </div>
              {canAuthor && (
                <div className="actions">
                  <button
                    className="button"
                    onClick={() => setEditing({ kind: "assignment", value: a })}
                  >
                    Edit assignment
                  </button>
                  <ActionButton onClick={() => remove("assignments", a.id)}>
                    Delete assignment
                  </ActionButton>
                </div>
              )}
              {can("submissions.create") && (
                <button
                  className="button"
                  onClick={() => setSubmitAssignment(a)}
                >
                  Submit work
                </button>
              )}
            </div>
          ))}
          {assignments.data?.total === 0 && (
            <Empty>No assignments in this course yet.</Empty>
          )}
        </section>
      </div>
      <section className="panel info-panel">
        <h2>
          {can("assessments.grade")
            ? "Review queue & submission history"
            : "Your submissions & feedback"}
        </h2>
        <ErrorBox error={submissions.error} />
        {submissions.data?.items.map((s) => (
          <div className="submission-card" key={s.id}>
            <div className="section-heading">
              <div>
                <h3>{s.assignment_title}</h3>
                <p>
                  {s.student_name} · Version {s.version}{" "}
                  {s.late ? "· Late submission" : ""}
                </p>
              </div>
              <Badge>{s.status}</Badge>
            </div>
            <p className="prose">{s.text}</p>
            <div className="actions">
              {s.file_ids.map((fid, i) => (
                <ActionButton
                  key={fid}
                  onClick={() =>
                    download(`/files/${fid}/download`, `submission-${i + 1}`)
                  }
                >
                  Download file {i + 1}
                </ActionButton>
              ))}
              {can("assessments.grade") && (
                <button className="button primary" onClick={() => setGrade(s)}>
                  {s.grade ? "Update grade" : "Grade submission"}
                </button>
              )}
            </div>
            {s.grade && (
              <div className="feedback">
                <strong>{s.grade.marks} marks</strong>
                {s.feedback.map((f, i) => (
                  <p key={i}>{f.text}</p>
                ))}
              </div>
            )}
          </div>
        ))}
        {submissions.data?.total === 0 && (
          <Empty>No submissions to show yet.</Empty>
        )}
      </section>
      <section className="panel info-panel">
        <h2>Quiz attempt history</h2>
        <ErrorBox error={attempts.error} />
        {attempts.data?.items.map((a) => (
          <div className="assessment-row" key={a.id}>
            <div>
              <h3>{a.quiz_title}</h3>
              <p>
                {a.student_name} · <Badge>{a.status}</Badge>{" "}
                {a.result_released
                  ? `${a.score ?? "Pending"} / ${a.max_score}`
                  : "Result not released"}
              </p>
            </div>
            <Link to={`/attempts/${a.id}`} className="button">
              {a.status === "in_progress" ? "Resume attempt" : "Review attempt"}
            </Link>
          </div>
        ))}
        {attempts.data?.total === 0 && <Empty>No attempts yet.</Empty>}
      </section>
      {canAuthor && (
        <section className="panel info-panel">
          <h2>Question bank</h2>
          <ErrorBox error={bank.error} />
          {bank.isLoading ? (
            <Loading />
          ) : (
            bank.data?.items.map((q) => (
              <div className="assessment-row" key={q.id}>
                <div>
                  <h3>{q.prompt}</h3>
                  <Badge>{q.kind}</Badge> · {q.points} points
                </div>
                <div className="actions">
                  <button
                    className="button"
                    onClick={() => setEditing({ kind: "question", value: q })}
                  >
                    Edit question
                  </button>
                  <ActionButton onClick={() => remove("questions", q.id)}>
                    Delete question
                  </ActionButton>
                </div>
              </div>
            ))
          )}
          {bank.data?.total === 0 && <Empty>Add your first question.</Empty>}
        </section>
      )}
      {editing?.kind === "question" && (
        <QuestionForm
          courseId={courseId}
          initial={editing.value as Question}
          close={() => setEditing(null)}
        />
      )}
      {editing?.kind === "quiz" && (
        <QuizForm
          courseId={courseId}
          initial={editing.value}
          close={() => setEditing(null)}
        />
      )}
      {editing?.kind === "assignment" && (
        <AssignmentForm
          courseId={courseId}
          initial={editing.value as Assignment}
          close={() => setEditing(null)}
        />
      )}
      {modal === "question" && (
        <QuestionForm courseId={courseId} close={() => setModal("")} />
      )}
      {modal === "quiz" && (
        <QuizForm courseId={courseId} close={() => setModal("")} />
      )}
      {modal === "assignment" && (
        <AssignmentForm courseId={courseId} close={() => setModal("")} />
      )}
      {submitAssignment && (
        <SubmitForm
          assignment={submitAssignment}
          close={() => setSubmitAssignment(null)}
        />
      )}
      {grade && (
        <GradeForm
          submission={grade}
          assignment={assignments.data?.items.find(
            (a) => a.id === grade.assignment_id,
          )}
          close={() => setGrade(null)}
        />
      )}
    </>
  );
}
function QuestionForm({
  courseId,
  close,
  initial,
}: {
  courseId: string;
  close: () => void;
  initial?: Question;
}) {
  const [options, setOptions] = useState(
      initial?.options.map((o) => ({ text: o.text, correct: !!o.correct })) || [
        { text: "", correct: true },
        { text: "", correct: false },
      ],
    ),
    action = useAction();
  const fields: Field[] = [
    { name: "prompt", label: "Question", type: "textarea", required: true },
    {
      name: "kind",
      label: "Question type",
      type: "select",
      default: "single",
      options: ["single", "multiple", "boolean", "short"].map((value) => ({
        value,
        label:
          {
            single: "Single choice",
            multiple: "Multiple select",
            boolean: "True / false",
            short: "Short answer",
          }[value] || value,
      })),
    },
    { name: "category", label: "Question bank category", default: "General" },
    { name: "points", label: "Points", type: "number", min: 0.1, default: 1 },
    {
      name: "negative_points",
      label: "Penalty for wrong answer",
      type: "number",
      default: 0,
    },
    {
      name: "explanation",
      label: "Explanation (released with results)",
      type: "textarea",
    },
  ];
  return (
    <Modal title={initial ? "Edit question" : "Add a question"} onClose={close}>
      <DataForm
        initial={initial}
        fields={fields}
        label="Save question"
        onSubmit={async (v) => {
          await action.mutateAsync({
            path: initial ? `/questions/${initial.id}` : "/questions",
            method: initial ? "PUT" : "POST",
            body: {
              ...v,
              course_id: courseId,
              options: v.kind === "short" ? [] : options,
            },
          });
          close();
        }}
      >
        <div className="wide option-editor">
          <h3>Answer options</h3>
          <p className="muted">
            Mark the correct options. Short-answer questions ignore options;
            true/false questions require two.
          </p>
          {options.map((o, i) => (
            <div className="option-row" key={i}>
              <input
                aria-label={`Option ${i + 1}`}
                value={o.text}
                onChange={(e) =>
                  setOptions(
                    options.map((v, n) =>
                      n === i ? { ...v, text: e.target.value } : v,
                    ),
                  )
                }
              />
              <label>
                <input
                  type="checkbox"
                  checked={o.correct}
                  onChange={(e) =>
                    setOptions(
                      options.map((v, n) =>
                        n === i ? { ...v, correct: e.target.checked } : v,
                      ),
                    )
                  }
                />{" "}
                Correct
              </label>
              {options.length > 2 && (
                <button
                  type="button"
                  className="button small"
                  onClick={() => setOptions(options.filter((_, n) => n !== i))}
                >
                  Remove
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            className="button"
            onClick={() =>
              setOptions([...options, { text: "", correct: false }])
            }
          >
            Add option
          </button>
        </div>
      </DataForm>
    </Modal>
  );
}
function QuizForm({
  courseId,
  close,
  initial,
}: {
  courseId: string;
  close: () => void;
  initial?: Entity;
}) {
  const questions = useApi<Page<Question>>(
      `/questions?course_id=${courseId}&page_size=100`,
    ),
    [selected, setSelected] = useState<string[]>(
      (initial?.question_ids as string[]) || [],
    ),
    action = useAction();
  const fields: Field[] = [
    { name: "title", label: "Quiz title", required: true },
    {
      name: "time_limit_minutes",
      label: "Time limit (minutes)",
      type: "number",
      min: 1,
      max: 300,
      default: 30,
    },
    {
      name: "attempt_limit",
      label: "Maximum attempts",
      type: "number",
      min: 1,
      max: 20,
      default: 3,
    },
    {
      name: "pass_percent",
      label: "Pass percentage",
      type: "number",
      max: 100,
      default: 60,
    },
    {
      name: "sample_size",
      label: "Random sample size (0 = all)",
      type: "number",
      default: 0,
    },
    { name: "opens_at", label: "Opens at", type: "datetime-local" },
    { name: "closes_at", label: "Closes at", type: "datetime-local" },
    {
      name: "release_policy",
      label: "Result release",
      type: "select",
      default: "immediate",
      options: ["immediate", "after_close", "manual"].map((value) => ({
        value,
        label: value.replaceAll("_", " "),
      })),
    },
    {
      name: "required",
      label: "Required for completion",
      type: "checkbox",
      default: true,
    },
  ];
  return (
    <Modal title={initial ? "Edit quiz" : "Create quiz"} onClose={close}>
      <ErrorBox error={questions.error} />
      <DataForm
        initial={initial}
        fields={fields}
        onSubmit={async (v) => {
          if (!selected.length) throw new Error("Select at least one question");
          await action.mutateAsync({
            path: initial ? `/quizzes/${initial.id}` : "/quizzes",
            method: initial ? "PUT" : "POST",
            body: { ...v, course_id: courseId, question_ids: selected },
          });
          close();
        }}
      >
        <fieldset className="wide question-checks">
          <legend>Questions from your course bank</legend>
          {questions.data?.items.map((q) => (
            <label key={q.id}>
              <input
                type="checkbox"
                checked={selected.includes(q.id)}
                onChange={(e) =>
                  setSelected(
                    e.target.checked
                      ? [...selected, q.id]
                      : selected.filter((id) => id !== q.id),
                  )
                }
              />
              {q.prompt} <Badge>{q.kind}</Badge>
            </label>
          ))}
          {questions.data?.total === 0 && (
            <p>Add a question to the bank first.</p>
          )}
        </fieldset>
      </DataForm>
    </Modal>
  );
}
function AssignmentForm({
  courseId,
  close,
  initial,
}: {
  courseId: string;
  close: () => void;
  initial?: Assignment;
}) {
  const action = useAction(),
    [rubric, setRubric] = useState<{ title: string; max_marks: number }[]>(
      initial?.rubric.map((r) => ({
        title: r.title,
        max_marks: r.max_marks,
      })) || [],
    ),
    [files, setFiles] = useState<string[]>(initial?.file_ids || []);
  return (
    <Modal
      title={initial ? "Edit assignment" : "Create assignment"}
      onClose={close}
    >
      <FileUploader
        courseId={courseId}
        purpose="resource"
        onUploaded={(id) => setFiles([...files, id])}
      />
      {files.map((id, i) => (
        <div className="actions" key={id}>
          Resource {i + 1}
          <button
            className="button small"
            onClick={() => setFiles(files.filter((f) => f !== id))}
          >
            Remove attachment
          </button>
        </div>
      ))}
      <DataForm
        initial={initial}
        fields={[
          { name: "title", label: "Assignment title", required: true },
          {
            name: "instructions",
            label: "Instructions",
            type: "textarea",
            required: true,
          },
          { name: "due_at", label: "Due date", type: "datetime-local" },
          {
            name: "max_marks",
            label: "Maximum marks",
            type: "number",
            min: 1,
            default: 100,
          },
          {
            name: "pass_percent",
            label: "Pass percentage",
            type: "number",
            max: 100,
            default: 50,
          },
          {
            name: "max_submissions",
            label: "Maximum submission versions",
            type: "number",
            min: 1,
            max: 20,
            default: 3,
          },
          {
            name: "allow_late",
            label: "Allow late submissions",
            type: "checkbox",
          },
          {
            name: "required",
            label: "Required for completion",
            type: "checkbox",
            default: true,
          },
        ]}
        onSubmit={async (v) => {
          await action.mutateAsync({
            path: initial ? `/assignments/${initial.id}` : "/assignments",
            method: initial ? "PUT" : "POST",
            body: { ...v, course_id: courseId, rubric, file_ids: files },
          });
          close();
        }}
      >
        <div className="wide">
          <h3>Optional grading rubric</h3>
          {rubric.map((r, i) => (
            <div className="option-row" key={i}>
              <input
                aria-label={`Criterion ${i + 1}`}
                placeholder="Criterion"
                value={r.title}
                onChange={(e) =>
                  setRubric(
                    rubric.map((x, n) =>
                      n === i ? { ...x, title: e.target.value } : x,
                    ),
                  )
                }
              />
              <input
                type="number"
                aria-label={`Criterion ${i + 1} marks`}
                value={r.max_marks}
                onChange={(e) =>
                  setRubric(
                    rubric.map((x, n) =>
                      n === i ? { ...x, max_marks: Number(e.target.value) } : x,
                    ),
                  )
                }
              />
              <button
                type="button"
                className="button small"
                onClick={() => setRubric(rubric.filter((_, n) => n !== i))}
              >
                Remove
              </button>
            </div>
          ))}
          <button
            type="button"
            className="button"
            onClick={() => setRubric([...rubric, { title: "", max_marks: 50 }])}
          >
            Add rubric criterion
          </button>
          <small className="muted">
            Criterion totals must equal maximum marks.
          </small>
        </div>
      </DataForm>
    </Modal>
  );
}
function SubmitForm({
  assignment,
  close,
}: {
  assignment: Assignment;
  close: () => void;
}) {
  const [files, setFiles] = useState<string[]>([]),
    action = useAction();
  return (
    <Modal title={`Submit: ${assignment.title}`} onClose={close}>
      <p className="muted">Each submission creates a retained version.</p>
      <FileUploader
        courseId={assignment.course_id}
        purpose="submission"
        onUploaded={(id) => setFiles([...files, id])}
      />
      <p>{files.length} uploaded file(s)</p>
      <DataForm
        fields={[{ name: "text", label: "Your response", type: "textarea" }]}
        label="Submit assignment"
        onSubmit={async (v) => {
          await action.mutateAsync({
            path: `/assignments/${assignment.id}/submit`,
            body: { ...v, file_ids: files },
          });
          close();
        }}
      />
    </Modal>
  );
}
function GradeForm({
  submission,
  assignment,
  close,
}: {
  submission: Submission;
  assignment?: Assignment;
  close: () => void;
}) {
  const action = useAction();
  const rubric = assignment?.rubric || [];
  const fields: Field[] = [
    {
      name: "marks",
      label: `Total marks (maximum ${assignment?.max_marks || 100})`,
      type: "number",
      max: assignment?.max_marks || 100,
      default: submission.grade?.marks || 0,
    },
    ...rubric.map((r) => ({
      name: r.id,
      label: `${r.title} / ${r.max_marks}`,
      type: "number" as const,
      max: r.max_marks,
    })),
    { name: "feedback", label: "Feedback", type: "textarea" },
    {
      name: "released",
      label: "Release grade to learner",
      type: "checkbox",
      default: true,
    },
  ];
  return (
    <Modal title={`Grade: ${submission.student_name}`} onClose={close}>
      <DataForm
        fields={fields}
        onSubmit={async (v) => {
          const scores = Object.fromEntries(rubric.map((r) => [r.id, v[r.id]]));
          await action.mutateAsync({
            path: `/submissions/${submission.id}/grade`,
            method: "PUT",
            body: {
              marks: v.marks,
              feedback: v.feedback,
              released: v.released,
              rubric_scores: scores,
            },
          });
          close();
        }}
      />
    </Modal>
  );
}
export function AttemptPage() {
  const { id } = useParams(),
    auth = useAuth(),
    query = useApi<Attempt>(`/attempts/${id}`),
    client = useQueryClient();
  const [answers, setAnswers] = useState<
      Record<string, { selected: string[]; text: string }>
    >({}),
    [tick, setTick] = useState(Date.now()),
    [dirty, setDirty] = useState(false),
    [message, setMessage] = useState("");
  const initialized = useRef(""),
    offset = useRef(0);
  useEffect(() => {
    if (query.data && initialized.current !== query.data.id) {
      initialized.current = query.data.id;
      offset.current = new Date(query.data.server_time).getTime() - Date.now();
      setAnswers(
        Object.fromEntries(
          query.data.answers.map((a) => [
            a.question_id,
            { selected: a.value.selected || [], text: a.value.text || "" },
          ]),
        ),
      );
    }
  }, [query.data]);
  useEffect(() => {
    const timer = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  if (query.isLoading) return <Loading />;
  if (!query.data) return <ErrorBox error={query.error} />;
  const a = query.data,
    own = a.user_id === auth.user?.id,
    active = a.status === "in_progress" && own,
    remaining = Math.max(
      0,
      Math.floor(
        (new Date(a.deadline).getTime() - tick - offset.current) / 1000,
      ),
    );
  const update = (qid: string, value: { selected: string[]; text: string }) => {
    setAnswers({ ...answers, [qid]: value });
    setDirty(true);
    setMessage("");
  };
  const save = async () => {
    await send(
      `/attempts/${a.id}/answers`,
      {
        answers: Object.entries(answers).map(([question_id, v]) => ({
          question_id,
          ...v,
        })),
      },
      "PUT",
    );
    setDirty(false);
    setMessage("Answers saved to the server.");
  };
  return (
    <>
      <Link to="/assessments" className="text-link back-link">
        <ArrowLeft size={16} /> Assessments
      </Link>
      <Heading
        eyebrow="QUIZ WORKSPACE"
        title={a.quiz_title}
        description={
          active
            ? "Save your answers regularly. The server enforces the deadline."
            : `Status: ${a.status.replaceAll("_", " ")}`
        }
      >
        <Badge>{a.status}</Badge>
        {active && (
          <span className="quiz-timer">
            <Timer size={18} />
            {Math.floor(remaining / 60)}:
            {String(remaining % 60).padStart(2, "0")}
          </span>
        )}
      </Heading>
      <ErrorBox error={query.error} />
      {a.result_released && (
        <div className="result-banner">
          <CheckCircle2 size={26} />
          <div>
            <strong>
              {a.score ?? "Pending"} / {a.max_score}
            </strong>
            <span>Released result</span>
          </div>
        </div>
      )}
      {a.questions.map((q, index) => {
        const answer = answers[q.id] || { selected: [], text: "" },
          graded = a.answers.find((x) => x.question_id === q.id);
        return (
          <section className="panel quiz-question" key={q.id}>
            <div className="question-number">
              QUESTION {index + 1} <span>{q.points} points</span>
            </div>
            <h2>{q.prompt}</h2>
            {q.kind === "short" ? (
              <textarea
                aria-label={`Answer to question ${index + 1}`}
                rows={5}
                disabled={!active || remaining === 0}
                value={answer.text}
                onChange={(e) =>
                  update(q.id, { ...answer, text: e.target.value })
                }
              />
            ) : (
              <fieldset disabled={!active || remaining === 0}>
                <legend className="sr-only">Answer choices</legend>
                {q.options.map((o) => (
                  <label
                    className={`answer-option ${o.correct ? "correct-option" : ""}`}
                    key={o.id}
                  >
                    <input
                      type={q.kind === "multiple" ? "checkbox" : "radio"}
                      name={q.id}
                      checked={answer.selected.includes(o.id)}
                      onChange={(e) =>
                        update(q.id, {
                          ...answer,
                          selected:
                            q.kind === "multiple"
                              ? e.target.checked
                                ? [...answer.selected, o.id]
                                : answer.selected.filter((id) => id !== o.id)
                              : [o.id],
                        })
                      }
                    />
                    <span>{o.text}</span>
                    {o.correct && <CheckCircle2 size={18} />}
                  </label>
                ))}
              </fieldset>
            )}
            {a.result_released && (
              <p className="feedback">
                {graded?.marks ?? "Awaiting manual review"} marks ·{" "}
                {q.explanation || graded?.feedback}
              </p>
            )}
            {!own &&
              auth.can("assessments.grade") &&
              q.kind === "short" &&
              graded && (
                <ManualGrade
                  attemptId={a.id}
                  answer={graded}
                  maximum={q.points}
                />
              )}
          </section>
        );
      })}
      {active && (
        <div className="quiz-bottom">
          <span className={dirty ? "warning-text" : "teal"}>
            {dirty
              ? "You have unsaved changes"
              : message || "Your saved answers persist on the server"}
          </span>
          <div className="actions">
            <ActionButton onClick={save}>Save answers</ActionButton>
            <ActionButton
              className="button primary"
              onClick={async () => {
                if (
                  !confirm(
                    "Submit this quiz attempt? Answers cannot be changed after submission.",
                  )
                )
                  return;
                if (remaining > 0) await save();
                await send(`/attempts/${a.id}/submit`);
                await client.invalidateQueries();
              }}
            >
              Submit attempt
            </ActionButton>
          </div>
        </div>
      )}
    </>
  );
}
function ManualGrade({
  attemptId,
  answer,
  maximum,
}: {
  attemptId: string;
  answer: Answer;
  maximum: number;
}) {
  const action = useAction();
  return (
    <DataForm
      fields={[
        {
          name: "marks",
          label: `Manual score / ${maximum}`,
          type: "number",
          max: maximum,
          default: answer.marks || 0,
        },
        { name: "feedback", label: "Feedback", type: "textarea" },
      ]}
      label="Save answer grade"
      onSubmit={(v) =>
        action.mutateAsync({
          path: `/attempts/${attemptId}/answers/${answer.id}/grade`,
          method: "PUT",
          body: v,
        })
      }
    />
  );
}
