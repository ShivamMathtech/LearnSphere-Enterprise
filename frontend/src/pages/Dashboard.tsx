import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  GraduationCap,
  Users,
  Clock,
  Sparkles,
} from "lucide-react";
import {
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useAuth } from "../app/Auth";
import { useApi } from "../hooks/api";
import {
  Badge,
  Empty,
  ErrorBox,
  Heading,
  Loading,
  ProgressBar,
  date,
} from "../components/UI";
import type { DashboardData } from "../types/domain";
export function Dashboard() {
  const { user, can } = useAuth();
  const query = useApi<DashboardData>("/reports/dashboard");
  if (query.isLoading) return <Loading />;
  return (
    <>
      <Heading
        eyebrow="YOUR LEARNING, AT A GLANCE"
        title={`Welcome back, ${user?.name.split(" ")[0]}.`}
        description="A clear view of your people, progress and possibilities."
      >
        {can("courses.create") && (
          <Link className="button primary" to="/courses/new">
            Create a course <ArrowUpRight size={17} />
          </Link>
        )}
      </Heading>
      <ErrorBox error={query.error} />
      {query.data && (
        <>
          <div className="stats-grid">
            {Object.entries(query.data.metrics).map(([label, value], index) => {
              const Icon = [BookOpen, Users, GraduationCap, Clock][index % 4];
              return (
                <div className="stat-card" key={label}>
                  <div className="stat-top">
                    <span>{label}</span>
                    <span className={`stat-icon tone-${index % 4}`}>
                      <Icon size={19} />
                    </span>
                  </div>
                  <strong>
                    {value}
                    {label.includes("rate") && "%"}
                  </strong>
                  <small>From your learning records</small>
                </div>
              );
            })}
          </div>
          <div className="dashboard-grid">
            <div>
              <section className="welcome-banner">
                <div>
                  <Badge>LEARNING IN FOCUS</Badge>
                  <h2>
                    Make room for
                    <br />
                    your next big idea.
                  </h2>
                  <p>
                    Build skills one lesson at a time.
                    <br />
                    Your next chapter starts here.
                  </p>
                  {can("courses.read") && (
                    <Link to="/courses" className="banner-link">
                      Explore courses <ArrowRight size={16} />
                    </Link>
                  )}
                </div>
                <div className="banner-art">
                  <div className="book book-one" />
                  <div className="book book-two" />
                  <div className="book book-three" />
                  <Sparkles className="sparkle" size={35} />
                  <div className="art-circle" />
                </div>
              </section>
              <section className="panel chart-panel">
                <div className="section-heading">
                  <div>
                    <h2>Learning momentum</h2>
                    <p>Enrollment and completion · Last 7 days</p>
                  </div>
                  <div className="chart-legend">
                    <span>
                      <i /> Enrolled
                    </span>
                    <span>
                      <i /> Completed
                    </span>
                  </div>
                </div>
                {query.data.trend.length ? (
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height={245}>
                      <AreaChart
                        data={query.data.trend}
                        margin={{ top: 15, right: 12, left: -25, bottom: 0 }}
                      >
                        <defs>
                          <linearGradient
                            id="enrollFill"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="0%"
                              stopColor="#159b8d"
                              stopOpacity={0.22}
                            />
                            <stop
                              offset="100%"
                              stopColor="#159b8d"
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid
                          strokeDasharray="3 4"
                          vertical={false}
                          stroke="var(--line)"
                        />
                        <XAxis
                          dataKey="date"
                          tickFormatter={(d) =>
                            new Date(d).toLocaleDateString([], {
                              weekday: "short",
                            })
                          }
                          axisLine={false}
                          tickLine={false}
                          fontSize={11}
                        />
                        <YAxis
                          allowDecimals={false}
                          axisLine={false}
                          tickLine={false}
                          fontSize={11}
                        />
                        <Tooltip
                          contentStyle={{
                            borderRadius: 12,
                            background: "var(--panel)",
                            border: "1px solid var(--line)",
                          }}
                        />
                        <Area
                          dataKey="enrollments"
                          type="monotone"
                          stroke="#159b8d"
                          strokeWidth={2.5}
                          fill="url(#enrollFill)"
                        />
                        <Area
                          dataKey="completions"
                          type="monotone"
                          stroke="#8c83cf"
                          strokeWidth={2}
                          fill="transparent"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <Empty>Choose an institution to explore its activity.</Empty>
                )}
              </section>
            </div>
            <aside className="panel deadlines">
              <div className="section-heading">
                <div>
                  <h2>Coming up</h2>
                  <p>Your upcoming deadlines</p>
                </div>
                <CalendarIcon />
              </div>
              {query.data.deadlines.length ? (
                query.data.deadlines.map((item) => (
                  <Link
                    to={`/courses/${item.course_id}`}
                    className="deadline-item"
                    key={item.id}
                  >
                    <div className="date-tile">
                      <b>{new Date(item.due_at).getDate()}</b>
                      <span>
                        {new Date(item.due_at).toLocaleDateString([], {
                          month: "short",
                        })}
                      </span>
                    </div>
                    <div>
                      <small>{item.kind}</small>
                      <strong>{item.title}</strong>
                      <p>{date(item.due_at)}</p>
                    </div>
                  </Link>
                ))
              ) : (
                <Empty>All clear. No upcoming deadlines.</Empty>
              )}
              <div className="side-note">
                <span>SMALL STEPS, REAL PROGRESS</span>
                <p>Consistency turns learning into a habit.</p>
              </div>
            </aside>
          </div>
          <section className="course-section">
            <div className="section-heading">
              <div>
                <h2>
                  {query.data.scope === "learner"
                    ? "Continue learning"
                    : "Course activity"}
                </h2>
                <p>Keep your learning community moving forward</p>
              </div>
              {can("courses.read") && (
                <Link to="/courses" className="text-link">
                  View all courses <ArrowRight size={16} />
                </Link>
              )}
            </div>
            <div className="course-grid">
              {query.data.courses.map((course, index) => (
                <Link
                  to={`/courses/${course.id}`}
                  className="course-card"
                  key={course.id}
                >
                  <div className={`course-cover cover-${index % 4}`}>
                    <span>{course.difficulty.toUpperCase()}</span>
                    <BookOpen size={56} strokeWidth={1.2} />
                    <div className="cover-orbit" />
                  </div>
                  <div className="course-card-body">
                    <Badge>{course.status}</Badge>
                    <h3>{course.title}</h3>
                    <p>
                      <Users size={14} /> {course.learners} learners
                    </p>
                    <div className="progress-label">
                      <span>Learning progress</span>
                      <b>{course.progress}%</b>
                    </div>
                    <ProgressBar value={course.progress} />
                  </div>
                </Link>
              ))}
            </div>
            {!query.data.courses.length && (
              <div className="panel">
                <Empty>
                  Your courses will appear here as you enroll or receive
                  assignments.
                </Empty>
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}
function CalendarIcon() {
  return <Clock size={20} className="muted" />;
}
