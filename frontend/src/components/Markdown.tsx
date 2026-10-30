import { useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy } from "lucide-react";

function CodeBlock({ children, lang }: { children: string; lang?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };
  return (
    <div className="codeblock" dir="ltr">
      <div className="codeblock-bar">
        <span>{lang || "code"}</span>
        <button onClick={copy} title="Copy">
          {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre>
        <code>{children}</code>
      </pre>
    </div>
  );
}

/**
 * Safe Markdown renderer (GFM tables, lists, code blocks with copy button).
 * Citations like [1] become clickable chips when `onCite` is given.
 */
export default function Markdown({ text, onCite }: { text: string; onCite?: (n: number) => void }) {
  const src = onCite ? text.replace(/\[(\d{1,2})\](?!\()/g, "[$1](#cite-$1)") : text;
  return (
    <div className="markdown" dir="auto">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            const m = href?.match(/^#cite-(\d+)$/);
            if (m && onCite) {
              return (
                <button className="cite" onClick={() => onCite(Number(m[1]))}>
                  {m[1]}
                </button>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
          code({ className, children }) {
            const content = String(children ?? "");
            const lang = /language-(\w+)/.exec(className || "")?.[1];
            if (lang || content.includes("\n")) return <CodeBlock lang={lang}>{content.replace(/\n$/, "")}</CodeBlock>;
            return <code className="inline">{children as ReactNode}</code>;
          },
          pre({ children }) {
            return <>{children}</>;
          },
          table({ children }) {
            return (
              <div className="table-wrap">
                <table className="table">{children}</table>
              </div>
            );
          },
        }}
      >
        {src}
      </ReactMarkdown>
    </div>
  );
}
