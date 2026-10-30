import type { ReactNode } from "react";

/** Tiny, safe Markdown renderer for AI answers (no HTML injection). */
function inline(text: string, onCite?: (n: number) => void): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) parts.push(<strong key={i++}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`")) parts.push(<code key={i++}>{tok.slice(1, -1)}</code>);
    else {
      const n = Number(tok.slice(1, -1));
      parts.push(
        <button key={i++} className="cite" onClick={() => onCite?.(n)}>
          {n}
        </button>,
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export default function Markdown({ text, onCite }: { text: string; onCite?: (n: number) => void }) {
  const blocks: ReactNode[] = [];
  const lines = text.split("\n");
  let list: string[] = [];
  let code: string[] | null = null;
  const flushList = () => {
    if (list.length) {
      blocks.push(
        <ul key={blocks.length}>
          {list.map((l, i) => (
            <li key={i}>{inline(l, onCite)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line.startsWith("```")) {
      if (code) {
        blocks.push(<pre key={blocks.length}><code>{code.join("\n")}</code></pre>);
        code = null;
      } else {
        flushList();
        code = [];
      }
      continue;
    }
    if (code) {
      code.push(raw);
      continue;
    }
    const li = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)$/);
    if (li) {
      list.push(li[1]);
      continue;
    }
    flushList();
    if (!line.trim()) continue;
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) blocks.push(<h4 key={blocks.length}>{inline(h[2], onCite)}</h4>);
    else blocks.push(<p key={blocks.length}>{inline(line, onCite)}</p>);
  }
  flushList();
  if (code) blocks.push(<pre key={blocks.length}><code>{(code as string[]).join("\n")}</code></pre>);
  return <div className="markdown" dir="auto">{blocks}</div>;
}
