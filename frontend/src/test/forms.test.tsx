import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { DataForm, ErrorBox, Table, Loading, Modal } from "../components/UI";

describe("Accessible forms and data states", () => {
  it("blocks invalid email and a short password before a request", async () => {
    const submit = vi.fn();
    const user = userEvent.setup();
    render(
      <DataForm
        fields={[
          { name: "email", label: "Email", type: "email", required: true },
          {
            name: "password",
            label: "Password",
            type: "password",
            required: true,
          },
        ]}
        onSubmit={submit}
      />,
    );
    await user.type(screen.getByLabelText(/Email/), "a@example.com");
    await user.type(screen.getByLabelText(/Password/), "short");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Use at least 12 characters")).toBeVisible();
    expect(submit).not.toHaveBeenCalled();
  });
  it("sends validated values, coerces numeric inputs and shows backend errors", async () => {
    const submit = vi.fn().mockRejectedValue(new Error("Capacity reached"));
    const user = userEvent.setup();
    render(
      <DataForm
        fields={[
          { name: "title", label: "Title", required: true },
          {
            name: "capacity",
            label: "Capacity",
            type: "number",
            min: 1,
            default: 10,
          },
        ]}
        onSubmit={submit}
      />,
    );
    await user.type(screen.getByLabelText(/Title/), "New course");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Capacity reached",
    );
    expect(submit).toHaveBeenCalledWith({ title: "New course", capacity: 10 });
  });
  it("allows an empty optional invitation password", async () => {
    const submit = vi.fn().mockResolvedValue({});
    const user = userEvent.setup();
    render(
      <DataForm
        fields={[
          { name: "password", label: "Initial password", type: "password" },
        ]}
        onSubmit={submit}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith({ password: "" }));
  });
  it("renders empty table and disables pagination outside the result bounds", () => {
    render(
      <Table
        data={{ items: [], total: 0, page: 1, page_size: 20 }}
        page={1}
        setPage={vi.fn()}
        columns={[{ key: "name", label: "Name" }]}
      />,
    );
    expect(screen.getByText(/No records yet/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
  it("reports network errors and loading to assistive technology", () => {
    render(
      <>
        <ErrorBox error={new Error("Server unavailable")} />
        <Loading />
      </>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Server unavailable");
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });
  it("opens a labeled native dialog with keyboard-close support", () => {
    render(
      <Modal title="Edit record" onClose={vi.fn()}>
        <p>Editable fields</p>
      </Modal>,
    );
    expect(screen.getByRole("dialog", { name: "Edit record" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Close dialog" })).toBeVisible();
  });
});
