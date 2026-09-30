import type { ButtonHTMLAttributes, LabelHTMLAttributes, ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`border-2 border-ink bg-paper-raised p-6 shadow-[var(--block-1)] ${className}`}>
      {children}
    </div>
  );
}

export function PageTitle({ children }: { children: ReactNode }) {
  return (
    <h1 className="font-mast mb-2 text-[length:var(--fs-display)] leading-[1.05] font-normal tracking-[-0.01em]">
      {children}
    </h1>
  );
}

export function Lede({ children }: { children: ReactNode }) {
  return <p className="mb-8 max-w-[65ch] text-ink-soft">{children}</p>;
}

export function Field({
  label,
  children,
  ...props
}: LabelHTMLAttributes<HTMLLabelElement> & { label: ReactNode; children: ReactNode }) {
  return (
    <label {...props} className="mb-4 block">
      <span className="kicker mb-1 block text-ink">{label}</span>
      {children}
    </label>
  );
}

const inputClasses =
  "font-gothic min-h-12 w-full rounded-none border-2 border-ink bg-paper-raised px-3 py-2 text-base text-ink focus:shadow-[var(--block-genre)]";

export function textInputClasses(extra = ""): string {
  return `${inputClasses} ${extra}`.trim();
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const base =
    "font-gothic min-h-12 rounded-none border-2 px-5 py-2 text-base font-bold tracking-[0.06em] uppercase " +
    "transition-[transform,box-shadow] duration-[var(--dur-fast)] ease-[var(--ease-press)] " +
    "enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-[4px_4px_0_var(--ink)] " +
    "enabled:active:translate-x-[3px] enabled:active:translate-y-[3px] enabled:active:shadow-none " +
    "disabled:cursor-not-allowed disabled:border-dashed disabled:opacity-45";
  const variants: Record<string, string> = {
    primary: "border-ink bg-ink text-paper shadow-[var(--block-genre)]",
    secondary: "border-ink bg-paper-raised text-ink shadow-[var(--block-1)]",
    danger: "border-press-red bg-paper-raised text-press-red shadow-[3px_3px_0_var(--press-red)]",
  };
  return <button {...props} className={`${base} ${variants[variant]} ${className}`} />;
}

/** Telegram slip: dashed top and bottom, with a text label so kind is never colour-only. */
export function Notice({
  kind,
  children,
}: {
  kind: "error" | "success" | "info";
  children: ReactNode;
}) {
  const styles: Record<string, string> = {
    error: "text-danger",
    success: "text-success",
    info: "text-ink-soft",
  };
  const labels: Record<string, string> = { error: "Problem", success: "Done", info: "Note" };
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className="font-gothic mb-6 border-y-2 border-dashed border-ink bg-paper-raised px-4 py-3 text-sm"
    >
      <span className={`kicker mr-2 ${styles[kind]}`}>{labels[kind]}</span>
      <span className="text-ink">{children}</span>
    </div>
  );
}
