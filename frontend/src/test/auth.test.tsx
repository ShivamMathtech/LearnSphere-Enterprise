import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../app/Auth";
import { LoginPage } from "../pages/AuthPages";
import { SidebarLinks } from "../layouts/Shell";
import { refreshSession, send } from "../services/api";
vi.mock("../services/api", () => ({
  refreshSession: vi.fn(),
  send: vi.fn(),
  setToken: vi.fn(),
  setInstitution: vi.fn(),
  get: vi.fn(),
  errorText: (e: Error) => e.message,
}));
const student = {
  id: "student",
  name: "Student Learner",
  email: "student@example.com",
  institution_id: "one",
  roles: ["student"],
  permissions: ["courses.read", "progress.update", "certificates.read"],
  mfa_enabled: false,
  verified: true,
};
function wrapper(children: React.ReactNode) {
  return (
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <AuthProvider>{children}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}
beforeEach(() => {
  vi.clearAllMocks();
});
describe("Authentication and role-aware navigation", () => {
  it("shows only learner navigation after restoring a session", async () => {
    vi.mocked(refreshSession).mockResolvedValue({
      access_token: "access",
      expires_in: 600,
      user: student,
    });
    render(wrapper(<SidebarLinks />));
    expect(
      await screen.findByRole("link", { name: "Course catalog" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "People" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Configuration" }),
    ).not.toBeInTheDocument();
  });
  it("keeps a failed login on the form with a useful error", async () => {
    vi.mocked(refreshSession).mockRejectedValue(new Error("No session"));
    vi.mocked(send).mockRejectedValue(
      new Error("Invalid credentials or account temporarily locked"),
    );
    const user = userEvent.setup();
    render(wrapper(<LoginPage />));
    await user.type(
      screen.getByLabelText(/Email address/),
      "student@example.com",
    );
    await user.type(screen.getByLabelText(/^Password/), "WrongPassword2026!");
    await user.click(
      screen.getByRole("button", { name: "Sign in to your workspace" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid credentials",
    );
    expect(send).toHaveBeenCalledWith("/auth/login", {
      email: "student@example.com",
      password: "WrongPassword2026!",
      totp: null,
    });
  });
  it("accepts a successful login and reveals the authorized workspace links", async () => {
    vi.mocked(refreshSession).mockRejectedValue(new Error("No session"));
    vi.mocked(send).mockResolvedValue({
      access_token: "access",
      expires_in: 600,
      user: student,
    });
    const user = userEvent.setup();
    render(
      wrapper(
        <>
          <LoginPage />
          <SidebarLinks />
        </>,
      ),
    );
    await user.type(
      screen.getByLabelText(/Email address/),
      "student@example.com",
    );
    await user.type(screen.getByLabelText(/^Password/), "StrongPassword2026!");
    await user.click(
      screen.getByRole("button", { name: "Sign in to your workspace" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "My learning" })).toBeVisible(),
    );
  });
});
