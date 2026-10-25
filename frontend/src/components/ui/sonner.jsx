import { Toaster as Sonner } from "sonner";

import { useTheme } from "@/components/theme-context";

function Toaster(props) {
  const { theme } = useTheme();

  return (
    <Sonner
      theme={theme}
      position="top-right"
      closeButton
      richColors
      toastOptions={{
        classNames: {
          toast:
            "!rounded-xl !border-border !bg-popover !text-popover-foreground !shadow-xl",
          description: "!text-muted-foreground",
          actionButton: "!bg-primary !text-primary-foreground",
        },
      }}
      {...props}
    />
  );
}

export { Toaster };
