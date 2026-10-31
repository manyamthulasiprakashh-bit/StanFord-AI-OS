import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/useAuth";

export default function LoginPage() {
  const { login, status } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);

    try {
      await login({ username, password });
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Login failed. Please try again.",
      );
    }
  }

  const isSubmitting = status === "authenticating";

  return (
    <section className="card">
      <h2>Login</h2>
      <p>Sign in with your Stanford-AI OS account.</p>

      <form onSubmit={handleSubmit} aria-labelledby="login-heading">
        <h3 id="login-heading" className="visually-hidden">
          Login
        </h3>

        <label>
          Username
          <input
            type="text"
            name="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
          />
        </label>

        <label>
          Password
          <input
            type="password"
            name="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {errorMessage ? <p role="alert">{errorMessage}</p> : null}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </section>
  );
}
