import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Layers, Repeat, GitBranch, Palette, Shield, Rocket, FileCode2, Eye } from "lucide-react"

const features = [
  {
    icon: Repeat,
    title: "Smart Component Reuse",
    description: "AI-powered semantic matching finds similar components across your projects. Reuse up to 70% of existing code.",
    color: "text-violet-500",
    bgColor: "bg-violet-500/10",
  },
  {
    icon: Layers,
    title: "Add Pages Easily",
    description: "Extend existing projects with new pages. No need to rebuild from scratch - just add and deploy.",
    color: "text-purple-500",
    bgColor: "bg-purple-500/10",
  },
  {
    icon: Palette,
    title: "Design System Sync",
    description: "Maintain consistent UI across all pages. Colors, typography, and spacing stay perfectly aligned.",
    color: "text-fuchsia-500",
    bgColor: "bg-fuchsia-500/10",
  },
  {
    icon: FileCode2,
    title: "Production-Ready Code",
    description: "Clean React + TypeScript with Tailwind CSS. ESLint, Prettier, and accessibility built-in.",
    color: "text-blue-500",
    bgColor: "bg-blue-500/10",
  },
  {
    icon: Eye,
    title: "Visual Verification",
    description: "Automated screenshot comparison ensures your generated code matches the original Figma design.",
    color: "text-green-500",
    bgColor: "bg-green-500/10",
  },
  {
    icon: GitBranch,
    title: "GitHub + Vercel Deploy",
    description: "Auto-create repos, branches, and PRs. One-click deployment to Vercel with CI/CD ready.",
    color: "text-orange-500",
    bgColor: "bg-orange-500/10",
  },
]

export function Features() {
  return (
    <section className="py-16 md:py-24">
      <div className="container mx-auto px-4">
        {/* Section header */}
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Enterprise-Grade Features for{" "}
            <span className="bg-gradient-to-r from-violet-600 to-purple-600 bg-clip-text text-transparent">
              Modern Teams
            </span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Built for scale. Our platform helps large teams maintain consistency
            while shipping faster than ever.
          </p>
        </div>

        {/* Features grid */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature, index) => {
            const Icon = feature.icon
            return (
              <Card
                key={feature.title}
                className="group relative overflow-hidden border-border/50 hover:border-primary/50 transition-all duration-300 hover:shadow-lg hover:shadow-primary/5 animate-fade-in-up"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                {/* Hover gradient */}
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                <CardHeader className="relative">
                  <div className={`w-12 h-12 rounded-lg ${feature.bgColor} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                    <Icon className={`h-6 w-6 ${feature.color}`} />
                  </div>
                  <CardTitle className="text-xl">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent className="relative">
                  <CardDescription className="text-base">
                    {feature.description}
                  </CardDescription>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* USP highlight box */}
        <div className="mt-16 p-8 rounded-2xl bg-gradient-to-r from-violet-600/10 via-purple-600/10 to-fuchsia-600/10 border border-primary/20">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center shadow-lg shadow-purple-500/25">
                <Rocket className="h-8 w-8 text-white" />
              </div>
              <div>
                <h3 className="text-xl font-bold">Why Choose Aura?</h3>
                <p className="text-muted-foreground">
                  70% faster development • Consistent design governance • Zero rebuild for new pages
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-500/10 text-green-600 dark:text-green-400">
                <Shield className="h-5 w-5" />
                <span className="font-medium">Enterprise Ready</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
