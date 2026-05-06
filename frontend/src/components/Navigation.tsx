import { Link, useLocation } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { LayoutDashboard, Package, Github, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"

export function Navigation() {
  const location = useLocation()

  const navItems = [
    { path: "/", label: "Dashboard", icon: LayoutDashboard },
    { path: "/components", label: "Components", icon: Package },
  ]

  return (
    <nav className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-lg supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 group">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-violet-600 to-purple-600 rounded-lg blur opacity-50 group-hover:opacity-75 transition-opacity" />
            <div className="relative w-9 h-9 bg-gradient-to-br from-violet-600 to-purple-600 rounded-lg flex items-center justify-center shadow-lg">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
          </div>
          <span className="text-xl font-bold bg-gradient-to-r from-violet-600 to-purple-600 bg-clip-text text-transparent">
            Aura
          </span>
        </Link>

        {/* Navigation Items */}
        <div className="flex items-center gap-1">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path
            return (
              <Button
                key={item.path}
                asChild
                variant="ghost"
                size="sm"
                className={cn(
                  "relative px-4 transition-all",
                  isActive && "text-primary"
                )}
              >
                <Link to={item.path} className="flex items-center gap-2">
                  <Icon className={cn("h-4 w-4", isActive && "text-violet-500")} />
                  {item.label}
                  {isActive && (
                    <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1/2 h-0.5 bg-gradient-to-r from-violet-600 to-purple-600 rounded-full" />
                  )}
                </Link>
              </Button>
            )
          })}

          <div className="w-px h-6 bg-border mx-2" />

          {/* GitHub Link */}
          <Button
            asChild
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-foreground"
          >
            <a
              href="https://github.com/manaspros/Aura-agent"
              target="_blank"
              rel="noopener noreferrer"
              title="View on GitHub"
            >
              <Github className="h-5 w-5" />
            </a>
          </Button>
        </div>
      </div>
    </nav>
  )
}
