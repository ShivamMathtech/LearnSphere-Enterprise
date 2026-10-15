import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import {
  GraduationCap,
  ArrowUpRight,
  ShieldCheck,
  BookOpen,
} from "lucide-react";
import { useAuth } from "../app/Auth";
import { DataForm, ErrorBox, Loading, type Field } from "../components/UI";
import { send } from "../services/api";
import { useApi } from "../hooks/api";
import type { Entity } from "../types/domain";
const loginFields: Field[] = [
  { name: "email", label: "Email address", type: "email", required: true },
  { name: "password", label: "Password", type: "password", required: true },
  {
    name: "totp",
    label: "Authenticator code",
    help: "Only if two-step verification is enabled.",
  },
];
export function LoginPage() {
  const auth = useAuth(),
    navigate = useNavigate();
  if (auth.user) return <Navigate to="/" replace />;
  return (
    <main className="login-layout">
      <section className="login-story">
        <div className="brand">
          <GraduationCap size={31} />
          <div>
            LearnSphere<span>ENTERPRISE</span>
          </div>
        </div>
        <div>
          <span className="eyebrow">A PLACE TO KEEP GROWING</span>
          <h1>
            Great learning.
            <br />
            Lasting impact.
          </h1>
          <p>
            Bring your institution, educators and learners together in one
            thoughtfully connected workspace.
          </p>
          <div className="login-art">
            <div className="orb orb-one" />
            <div className="orb orb-two" />
            <BookOpen size={90} strokeWidth={1} />
            <span className="art-label">
              CURIOUS MINDS. SHARED POSSIBILITIES.
            </span>
          </div>
        </div>
        <small>
          <ShieldCheck size={16} /> Your institution. Your learning journey.
        </small>
      </section>
      <section className="login-form">
        <div className="mobile-brand">
          <GraduationCap /> LearnSphere
        </div>
        <div className="eyebrow">WELCOME BACK</div>
        <h2>Continue your journey</h2>
        <p className="muted">Sign in with your institution account.</p>
        <DataForm
          fields={loginFields}
          label="Sign in to your workspace"
          onSubmit={async (values) => {
            await auth.login({ ...values, totp: values.totp || null });
            navigate("/");
          }}
        />
        <Link className="text-link" to="/forgot-password">
          Forgot your password? <ArrowUpRight size={15} />
        </Link>
        <div className="login-note">
          Need access? Ask your institution administrator for an account or
          invitation.
        </div>
      </section>
    </main>
  );
}
export function RecoveryPage({
  mode,
}: {
  mode: "forgot" | "reset" | "verify";
}) {
  const [message, setMessage] = useState("");
  const token = new URLSearchParams(location.hash.slice(1)).get("token") || "";
  const fields: Field[] =
    mode === "forgot"
      ? [
          {
            name: "email",
            label: "Email address",
            type: "email",
            required: true,
          },
        ]
      : mode === "reset"
        ? [
            { name: "token", label: "Reset token", required: true },
            {
              name: "password",
              label: "New password",
              type: "password",
              required: true,
              help: "12+ characters, uppercase, lowercase and a number.",
            },
          ]
        : [{ name: "token", label: "Verification token", required: true }];
  return (
    <main className="auth-card">
      <GraduationCap size={35} />
      <h1>
        {mode === "forgot"
          ? "Recover your account"
          : mode === "reset"
            ? "Set a new password"
            : "Verify your email"}
      </h1>
      {message ? (
        <p role="status" className="success-box">
          {message}
        </p>
      ) : (
        <DataForm
          fields={fields}
          initial={{ token }}
          label="Continue"
          onSubmit={async (values) => {
            const result = await send<{ message: string }>(
              `/auth/${mode === "forgot" ? "forgot-password" : mode === "reset" ? "reset-password" : "verify-email"}`,
              values,
            );
            setMessage(result.message);
            history.replaceState(null, "", location.pathname);
          }}
        />
      )}
      <Link to="/login" className="text-link">
        Back to sign in
      </Link>
    </main>
  );
}
export function VerifyPage() {
  const { code } = useParams();
  const query = useApi<Entity>(`/certificates/verify/${code}`);
  return (
    <main className="auth-card">
      <ShieldCheck size={40} />
      <h1>Certificate verification</h1>
      {query.isLoading ? (
        <Loading />
      ) : (
        <>
          <ErrorBox error={query.error} />
          {query.data && (
            <>
              <div className={query.data.valid ? "success-box" : "error-box"}>
                {query.data.valid
                  ? "Valid certificate"
                  : "This certificate has been revoked"}
              </div>
              <h2>{String(query.data.course)}</h2>
              <p>
                {String(query.data.learner)} · {String(query.data.institution)}
              </p>
              <p className="muted">
                Issued{" "}
                {new Date(String(query.data.issued_at)).toLocaleDateString()}
              </p>
              <code>{code}</code>
            </>
          )}
        </>
      )}
      <Link to="/login" className="text-link">
        LearnSphere Enterprise
      </Link>
    </main>
  );
}
