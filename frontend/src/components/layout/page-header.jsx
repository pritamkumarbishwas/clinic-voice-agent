import { cn } from "@/lib/utils";

function PageHeader({
  icon: Icon,
  eyebrow,
  title,
  description,
  actions,
  className,
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between",
        className
      )}
    >
      <div className="flex min-w-0 items-start gap-4">
        {Icon && (
          <div className="hidden size-12 shrink-0 place-items-center rounded-2xl border border-primary/15 bg-primary/8 text-primary shadow-xs sm:grid">
            <Icon className="size-5.5" />
          </div>
        )}
        <div className="min-w-0">
          {eyebrow && (
            <p className="text-[10px] font-bold tracking-[0.18em] text-primary uppercase">
              {eyebrow}
            </p>
          )}
          <h1 className="text-balance mt-1 text-2xl font-extrabold tracking-tight sm:text-3xl">
            {title}
          </h1>
          {description && (
            <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              {description}
            </p>
          )}
        </div>
      </div>

      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {actions}
        </div>
      )}
    </div>
  );
}

export { PageHeader };
