import { ArrowRight } from "lucide-react"
import { GlassFold } from "@/components/ui/glass-fold"

export default function Home({ onStart }: { onStart: () => void }) {
  return (
    <div className="relative h-screen w-full overflow-hidden bg-black">
      <GlassFold className="absolute inset-0" />
      <div className="absolute inset-x-0 bottom-0 p-8 text-left text-white [text-shadow:0_2px_24px_rgba(0,0,20,0.6)] sm:p-14">
        <h1 className="max-w-3xl text-5xl font-bold leading-[1.05] tracking-tight sm:text-7xl">
          Chat that never goes down
        </h1>
        <p className="mt-4 max-w-xl text-xl font-medium text-white/85 sm:text-2xl">
          Fast, resilient AI conversations.
        </p>
        <button
          data-testid="get-started"
          onClick={onStart}
          className="group mt-8 inline-flex cursor-pointer items-center gap-2 rounded-full bg-white px-9 py-4 text-lg font-bold text-black transition [text-shadow:none] hover:bg-white/90"
        >
          Get started
          <ArrowRight className="size-5 transition-transform group-hover:translate-x-1" />
        </button>
      </div>
    </div>
  )
}
