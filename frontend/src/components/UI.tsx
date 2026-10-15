import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, Inbox, Loader2, Search, X } from "lucide-react";
import { errorText } from "../services/api";
import type { Entity, Page } from "../types/domain";
export const text = (row: Entity, key: string) => String(row[key] ?? "");
export const date = (value: unknown) =>
  value
    ? new Date(String(value)).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "—";
export function Badge({ children }: { children: ReactNode }) {
  return (
    <span
      className={`badge badge-${String(children).toLowerCase().replaceAll(" ", "-")}`}
    >
      {String(children).replaceAll("_", " ")}
    </span>
  );
}
export function ErrorBox({ error }: { error: unknown }) {
  return error ? (
    <div className="error-box" role="alert">
      <AlertCircle size={18} />
      <span>{errorText(error)}</span>
    </div>
  ) : null;
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <Loader2 className="spin" size={24} /> Loading…
    </div>
  );
}
export function Empty({
  children = "No records yet. New activity will appear here.",
}: {
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <Inbox size={30} />
      <p>{children}</p>
    </div>
  );
}
export function Heading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow || "WORKSPACE"}</div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      <div className="actions">{children}</div>
    </div>
  );
}
export function ProgressBar({ value }: { value: number }) {
  return (
    <div
      className="progress-track"
      role="progressbar"
      aria-label="Course progress"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div style={{ width: `${value}%` }} />
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog ref={ref} className="modal" onCancel={onClose} aria-label={title}>
      <div className="modal-head">
        <h2>{title}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close dialog"
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export interface Field {
  name: string;
  label: string;
  type?:
    | "text"
    | "email"
    | "password"
    | "number"
    | "textarea"
    | "select"
    | "checkbox"
    | "datetime-local";
  required?: boolean;
  options?: { value: string; label: string }[];
  help?: string;
  min?: number;
  max?: number;
  default?: unknown;
}
export function DataForm({
  fields,
  initial = {},
  onSubmit,
  label = "Save changes",
  busy = false,
  children,
}: {
  fields: Field[];
  initial?: Record<string, unknown>;
  onSubmit: (values: Record<string, unknown>) => Promise<unknown>;
  label?: string;
  busy?: boolean;
  children?: ReactNode;
}) {
  const id = useId(),
    [error, setError] = useState<unknown>(null);
  const schema = useMemo(
    () =>
      z.object(
        Object.fromEntries(
          fields.map((f) => {
            let value: z.ZodTypeAny;
            if (f.type === "checkbox") value = z.boolean();
            else if (f.type === "number")
              value = z.coerce
                .number()
                .min(f.min ?? 0)
                .max(f.max ?? 100000);
            else {
              let string = z.string();
              if (f.required) string = string.min(1, `${f.label} is required`);
              if (f.type === "email")
                string = string.email("Enter a valid email");
              if (f.type === "password")
                string = string.min(12, "Use at least 12 characters");
              value = string.max(f.type === "textarea" ? 50000 : 2000);
            }
            if (f.type === "password" && !f.required)
              value = z.union([value, z.literal("")]);
            return [f.name, value];
          }),
        ),
      ),
    [fields],
  );
  const defaults = Object.fromEntries(
    fields.map((f) => {
      let value =
        initial[f.name] ??
        f.default ??
        (f.type === "checkbox"
          ? false
          : f.type === "number"
            ? (f.min ?? 0)
            : "");
      if (f.type === "datetime-local" && value) {
        const timestamp = new Date(String(value));
        if (!Number.isNaN(timestamp.getTime())) {
          value = new Date(
            timestamp.getTime() - timestamp.getTimezoneOffset() * 60000,
          )
            .toISOString()
            .slice(0, 16);
        }
      }
      return [f.name, value];
    }),
  );
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Record<string, unknown>>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
  });
  return (
    <form
      className="data-form"
      onSubmit={handleSubmit(async (values) => {
        setError(null);
        try {
          const cleaned = { ...values };
          for (const f of fields) {
            if (f.type === "datetime-local" && cleaned[f.name])
              cleaned[f.name] = new Date(String(cleaned[f.name])).toISOString();
            if (
              !f.required &&
              cleaned[f.name] === "" &&
              (f.name.endsWith("_id") || f.type === "datetime-local")
            )
              cleaned[f.name] = null;
          }
          await onSubmit(cleaned);
        } catch (e) {
          setError(e);
        }
      })}
    >
      <ErrorBox error={error} />
      {fields.map((f) => (
        <div
          className={`field ${f.type === "textarea" ? "wide" : ""}`}
          key={f.name}
        >
          <label htmlFor={`${id}-${f.name}`}>
            {f.label}
            {f.required && <span aria-hidden="true"> *</span>}
          </label>
          {f.type === "textarea" ? (
            <textarea
              id={`${id}-${f.name}`}
              aria-label={f.label}
              aria-required={f.required}
              aria-describedby={f.help ? `${id}-${f.name}-help` : undefined}
              aria-errormessage={
                errors[f.name] ? `${id}-${f.name}-error` : undefined
              }
              rows={4}
              {...register(f.name)}
              aria-invalid={!!errors[f.name]}
            />
          ) : f.type === "select" ? (
            <select
              id={`${id}-${f.name}`}
              aria-label={f.label}
              aria-required={f.required}
              aria-invalid={!!errors[f.name]}
              {...register(f.name)}
            >
              <option value="">Select…</option>
              {f.options?.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              id={`${id}-${f.name}`}
              aria-label={f.label}
              aria-required={f.required}
              aria-describedby={f.help ? `${id}-${f.name}-help` : undefined}
              aria-errormessage={
                errors[f.name] ? `${id}-${f.name}-error` : undefined
              }
              type={f.type || "text"}
              {...register(f.name)}
              step={f.type === "number" ? "any" : undefined}
              aria-invalid={!!errors[f.name]}
            />
          )}
          {f.help && <small id={`${id}-${f.name}-help`}>{f.help}</small>}
          {errors[f.name] && (
            <small
              className="field-error"
              id={`${id}-${f.name}-error`}
              role="alert"
            >
              {String(errors[f.name]?.message)}
            </small>
          )}
        </div>
      ))}
      {children}
      <div className="form-footer">
        <button className="button primary" disabled={busy || isSubmitting}>
          {isSubmitting || busy ? "Saving…" : label}
        </button>
      </div>
    </form>
  );
}
export function Table({
  data,
  columns,
  actions,
  loading,
  error,
  page,
  setPage,
  search,
  setSearch,
}: {
  data?: Page<Entity>;
  columns: {
    key: string;
    label: string;
    render?: (row: Entity) => ReactNode;
  }[];
  actions?: (row: Entity) => ReactNode;
  loading?: boolean;
  error?: unknown;
  page: number;
  setPage: (page: number) => void;
  search?: string;
  setSearch?: (search: string) => void;
}) {
  return (
    <div className="panel">
      <div className="table-tools">
        {setSearch && (
          <label className="search-box">
            <Search size={17} />
            <input
              aria-label="Search records"
              placeholder="Search records…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </label>
        )}
        <span className="muted">{data?.total ?? 0} records</span>
      </div>
      <ErrorBox error={error} />
      {loading ? (
        <Loading />
      ) : !data?.items.length ? (
        <Empty />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c.key} scope="col">
                    {c.label}
                  </th>
                ))}
                {actions && <th scope="col">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id}>
                  {columns.map((c) => (
                    <td key={c.key}>
                      {c.render ? c.render(row) : text(row, c.key) || "—"}
                    </td>
                  ))}
                  {actions && (
                    <td>
                      <div className="actions">{actions(row)}</div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pagination">
        <span>
          Page {page} of{" "}
          {Math.max(1, Math.ceil((data?.total || 0) / (data?.page_size || 20)))}
        </span>
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
            disabled={!data || page * data.page_size >= data.total}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
export function ActionButton({
  onClick,
  children,
  className = "button small",
}: {
  onClick: () => Promise<unknown>;
  children: ReactNode;
  className?: string;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null);
  return (
    <span>
      <button
        className={className}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            await onClick();
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Working…" : children}
      </button>
      <ErrorBox error={error} />
    </span>
  );
}
