import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { LearningPlayer } from "../pages/Courses";
import { AttemptPage } from "../pages/Assessments";
import { useApi, useAction } from "../hooks/api";
import { send } from "../services/api";
vi.mock("../hooks/api", () => ({ useApi: vi.fn(), useAction: vi.fn() }));
vi.mock("../app/Auth", () => ({
  useAuth: () => ({ user: { id: "student" }, can: () => true }),
}));
vi.mock("../services/api", () => ({
  send: vi.fn(),
  download: vi.fn(),
  upload: vi.fn(),
  errorText: (e: Error) => e.message,
}));
function wrap(path: string, component: React.ReactNode) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/learn/:id" element={component} />
          <Route path="/attempts/:id" element={component} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}
beforeEach(() => vi.clearAllMocks());
describe("Learning interactions", () => {
  it("records lesson completion through the server without submitting a browser percentage", async () => {
    const mutate = vi.fn().mockResolvedValue({});
    vi.mocked(useAction).mockReturnValue({
      mutateAsync: mutate,
    } as unknown as ReturnType<typeof useAction>);
    vi.mocked(useApi).mockImplementation(
      (path: string) =>
        ({
          isLoading: false,
          data: path.startsWith("/courses")
            ? {
                id: "course",
                title: "Secure APIs",
                progress: {
                  percent: 0,
                  completed_lesson_ids: [],
                  remaining: [],
                  eligible: false,
                },
                sections: [
                  {
                    id: "section",
                    title: "Start",
                    lessons: [{ id: "lesson", title: "Authorization" }],
                  },
                ],
                enrollment: { id: "enrollment" },
              }
            : {
                id: "lesson",
                title: "Authorization",
                kind: "text",
                content: "Verify permissions on the server.",
                file_ids: [],
              },
        }) as ReturnType<typeof useApi>,
    );
    const user = userEvent.setup();
    render(wrap("/learn/course", <LearningPlayer />));
    await user.click(
      screen.getByRole("button", { name: "Mark lesson complete" }),
    );
    await waitFor(() =>
      expect(mutate).toHaveBeenCalledWith({
        path: "/progress/lesson/complete",
      }),
    );
  });
  it("renders locked lesson errors without showing lesson content", () => {
    vi.mocked(useAction).mockReturnValue({} as ReturnType<typeof useAction>);
    vi.mocked(useApi).mockImplementation((path: string) =>
      path.startsWith("/courses")
        ? ({
            isLoading: false,
            data: {
              title: "Secure APIs",
              sections: [
                {
                  id: "s",
                  title: "Start",
                  lessons: [{ id: "locked", title: "Locked lesson" }],
                },
              ],
            },
          } as ReturnType<typeof useApi>)
        : ({
            isLoading: false,
            error: new Error("Complete the prerequisite lesson first"),
          } as ReturnType<typeof useApi>),
    );
    render(wrap("/learn/course", <LearningPlayer />));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Complete the prerequisite",
    );
    expect(
      screen.queryByRole("button", { name: "Mark lesson complete" }),
    ).not.toBeInTheDocument();
  });
  it("persists selected quiz answers while keeping unreleased results hidden", async () => {
    vi.mocked(send).mockResolvedValue({});
    vi.mocked(useApi).mockReturnValue({
      isLoading: false,
      data: {
        id: "attempt",
        user_id: "student",
        quiz_title: "Security quiz",
        status: "in_progress",
        deadline: new Date(Date.now() + 120000).toISOString(),
        server_time: new Date().toISOString(),
        questions: [
          {
            id: "q",
            kind: "single",
            prompt: "Where do permissions belong?",
            points: 1,
            options: [
              { id: "server", text: "Server" },
              { id: "browser", text: "Browser" },
            ],
          },
        ],
        answers: [],
        result_released: false,
        score: null,
        max_score: 1,
      },
    } as unknown as ReturnType<typeof useApi>);
    const user = userEvent.setup();
    render(wrap("/attempts/attempt", <AttemptPage />));
    await user.click(screen.getByRole("radio", { name: "Server" }));
    await user.click(screen.getByRole("button", { name: "Save answers" }));
    await waitFor(() =>
      expect(send).toHaveBeenCalledWith(
        "/attempts/attempt/answers",
        { answers: [{ question_id: "q", selected: ["server"], text: "" }] },
        "PUT",
      ),
    );
    expect(screen.queryByText("Released result")).not.toBeInTheDocument();
  });
});
