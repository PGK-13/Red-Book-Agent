import Link from "next/link";
import type { ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost";

type StatCardProps = {
  label: string;
  value: string;
  delta?: string;
  tone?: "accent" | "success" | "warning" | "muted";
};

type ModuleCardProps = {
  title: string;
  description: string;
  status: string;
  actionLabel: string;
  href: string;
  secondaryActionLabel?: string;
  secondaryHref?: string;
};

type TableColumn = {
  header: string;
  width?: string;
};

type TableRow = Record<string, ReactNode>;

type DataTableProps = {
  columns: TableColumn[];
  rows: TableRow[];
};

type BadgeTone = "success" | "warning" | "danger" | "neutral" | "accent";

export function SectionCard({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-2xl border border-border bg-bg-surface shadow-[0_12px_30px_rgba(255,107,138,0.06)] ${className}`}
    >
      {children}
    </section>
  );
}

export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 border-b border-border px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="space-y-1">
        <h2 className="text-[18px] font-semibold tracking-tight text-text-primary">
          {title}
        </h2>
        {description ? (
          <p className="text-[13px] text-text-secondary">{description}</p>
        ) : null}
      </div>
      {action ? <div className="flex items-center gap-2">{action}</div> : null}
    </div>
  );
}

export function StatCard({ label, value, delta, tone = "muted" }: StatCardProps) {
  const toneClass =
    tone === "accent"
      ? "bg-accent/10 text-accent"
      : tone === "success"
        ? "bg-accent-green/10 text-accent-green"
        : tone === "warning"
          ? "bg-amber-500/10 text-amber-600"
        : "bg-bg-surface-dim text-text-secondary";

  return (
    <SectionCard className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-[13px] text-text-secondary">{label}</p>
          <p className="text-[28px] font-semibold leading-none tracking-tight text-text-primary">
            {value}
          </p>
        </div>
        {delta ? (
          <span className={`rounded-full px-2.5 py-1 text-[12px] ${toneClass}`}>
            {delta}
          </span>
        ) : null}
      </div>
    </SectionCard>
  );
}

export function ButtonLink({
  href,
  children,
  variant = "primary",
}: {
  href: string;
  children: ReactNode;
  variant?: ButtonVariant;
}) {
  const classes =
    variant === "primary"
      ? "bg-accent text-white hover:brightness-110"
      : variant === "ghost"
        ? "bg-transparent text-text-primary hover:bg-bg-surface-hover border border-border"
        : "bg-bg-surface text-text-primary hover:bg-bg-surface-hover border border-border";

  return (
    <Link
      href={href}
      className={`inline-flex items-center justify-center rounded-lg px-4 h-[40px] text-[14px] font-semibold transition-colors ${classes}`}
    >
      {children}
    </Link>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: BadgeTone;
}) {
  const toneClass =
    tone === "success"
      ? "bg-accent-green/10 text-accent-green"
      : tone === "warning"
        ? "bg-amber-500/10 text-amber-600"
        : tone === "danger"
          ? "bg-red-500/10 text-red-500"
          : tone === "accent"
            ? "bg-accent/10 text-accent"
            : "bg-bg-surface-dim text-text-secondary";

  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-[12px] font-medium ${toneClass}`}>
      {children}
    </span>
  );
}

export function ModuleCard({
  title,
  description,
  status,
  actionLabel,
  href,
  secondaryActionLabel,
  secondaryHref,
}: ModuleCardProps) {
  return (
    <SectionCard className="p-5">
      <div className="flex h-full flex-col gap-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-accent" />
              <p className="text-[14px] font-semibold text-text-primary">
                {title}
              </p>
            </div>
            <p className="text-[13px] leading-6 text-text-secondary">
              {description}
            </p>
          </div>
          <Badge tone="accent">{status}</Badge>
        </div>
        <div className="mt-auto flex flex-wrap gap-2">
          <ButtonLink href={href}>{actionLabel}</ButtonLink>
          {secondaryActionLabel && secondaryHref ? (
            <ButtonLink href={secondaryHref} variant="secondary">
              {secondaryActionLabel}
            </ButtonLink>
          ) : null}
        </div>
      </div>
    </SectionCard>
  );
}

export function DataTable({ columns, rows }: DataTableProps) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-bg-surface">
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-bg-surface-dim/60">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.header}
                  className="px-4 py-3 text-left text-[12px] font-semibold uppercase tracking-wide text-text-secondary"
                  style={column.width ? { width: column.width } : undefined}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="transition-colors hover:bg-bg-surface-hover">
                {columns.map((column) => (
                  <td key={column.header} className="px-4 py-4 text-[14px] text-text-primary">
                    {row[column.header]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function TimelineItem({
  title,
  description,
  time,
  tone = "neutral",
}: {
  title: string;
  description: string;
  time: string;
  tone?: BadgeTone;
}) {
  return (
    <div className="flex gap-3 rounded-xl border border-border bg-bg-surface p-4">
      <div className="mt-1 h-2.5 w-2.5 rounded-full bg-accent" />
      <div className="flex-1 space-y-1">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[14px] font-semibold text-text-primary">{title}</p>
          <Badge tone={tone}>{time}</Badge>
        </div>
        <p className="text-[13px] leading-6 text-text-secondary">{description}</p>
      </div>
    </div>
  );
}

export function ProgressBar({
  value,
  label,
}: {
  value: number;
  label: string;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-[13px] text-text-secondary">
        <span>{label}</span>
        <span>{value}%</span>
      </div>
      <div className="h-2 rounded-full bg-bg-surface-dim">
        <div
          className="h-2 rounded-full bg-accent"
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}
