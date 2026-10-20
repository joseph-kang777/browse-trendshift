import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import { App } from "./App"
import { TooltipProvider } from "@/components/ui/tooltip"
import { I18nProvider } from "@/i18n"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <TooltipProvider>
        <App />
      </TooltipProvider>
    </I18nProvider>
  </StrictMode>
)
