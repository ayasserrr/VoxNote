import { MessageCircleQuestion } from "lucide-react";
import AskPanel from "../components/AskPanel";
import { PageHeader } from "../components/ui";

export default function AskPage() {
  return (
    <div>
      <PageHeader icon={<MessageCircleQuestion size={22} />} title="Ask your library"
        subtitle="Questions are answered from every video and documentation site you have added, with citations." />
      <div className="card">
        <AskPanel />
      </div>
    </div>
  );
}
