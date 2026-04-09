import { AutoForzeView } from "@/components/AutoForzeView";

export const metadata = {
  title: "AutoForze Builder — TaskForze",
  description: "Describe your automation workflow and AutoForze will forge it in the background.",
};

export default function AutoForzePage() {
  return (
    <main className="min-h-screen bg-[#050510] p-4 xl:p-6 flex items-stretch">
      <div className="w-full">
        <AutoForzeView />
      </div>
    </main>
  );
}
