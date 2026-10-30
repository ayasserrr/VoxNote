import AskPanel from "../components/AskPanel";

export default function AskPage() {
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Ask your library</h1>
          <p className="muted">Questions are answered from every video you have processed, with timestamped citations.</p>
        </div>
      </div>
      <div className="card">
        <AskPanel />
      </div>
    </div>
  );
}
