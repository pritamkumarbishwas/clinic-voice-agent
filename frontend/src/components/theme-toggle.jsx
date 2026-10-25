import { MoonIcon, SunIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useTheme } from "@/components/theme-context";

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const nextTheme = theme === "dark" ? "light" : "dark";

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={`Switch to ${nextTheme} mode`}
          className="rounded-xl text-muted-foreground hover:text-foreground"
        >
          {theme === "dark" ? (
            <SunIcon className="size-4.5" />
          ) : (
            <MoonIcon className="size-4.5" />
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent>Switch to {nextTheme} mode</TooltipContent>
    </Tooltip>
  );
}

export { ThemeToggle };
