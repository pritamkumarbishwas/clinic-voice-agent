import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center justify-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide whitespace-nowrap [&>svg]:size-3",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary/10 text-primary dark:bg-primary/15",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground",
        destructive:
          "border-transparent bg-destructive/10 text-destructive dark:bg-destructive/15",
        outline: "border-border bg-background/60 text-foreground",
        success:
          "border-transparent bg-success/12 text-success dark:bg-success/15",
        warning:
          "border-transparent bg-warning/15 text-warning-foreground dark:bg-warning/15 dark:text-warning",
        info: "border-transparent bg-info/12 text-info dark:bg-info/15",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

function Badge({ className, variant, ...props }) {
  return (
    <span
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  );
}

export { Badge };
