import { documentUrl } from "../api";
import type { DocumentInfo } from "../types";
import { fmtBytes } from "../utils";

export default function DocumentButtons({ docs }: { docs: DocumentInfo[] }) {
  const pdf = docs.find((d) => d.format === "pdf");
  const md = docs.find((d) => d.format === "md");
  if (!pdf && !md) return null;
  return (
    <div className="doc-buttons">
      {pdf && (
        <>
          <a className="btn primary sm" href={documentUrl(pdf.id, true)} target="_blank" rel="noreferrer">
            View PDF
          </a>
          <a className="btn sm" href={documentUrl(pdf.id)}>
            ⬇ PDF{pdf.pages ? ` · ${pdf.pages} pages` : ""} · {fmtBytes(pdf.size_bytes)}
          </a>
        </>
      )}
      {md && (
        <a className="btn sm" href={documentUrl(md.id)}>
          ⬇ Markdown
        </a>
      )}
    </div>
  );
}
