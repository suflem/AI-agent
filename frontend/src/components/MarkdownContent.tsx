import { useMemo, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import { toast } from "../services/toast";

type MarkdownContentProps = {
  content: string;
  className?: string;
};

function classifyLine(line: string) {
  const text = line.trim();
  if (!text) return "";
  if (/(^|\s)(error|failed|exception|traceback|失败|错误|异常|❌)/i.test(text)) return "line-alert";
  if (/(^|\s)(warn|warning|警告|注意|⚠️)/i.test(text)) return "line-warn";
  if (/(^|\s)(success|done|ok|通过|成功|完成|✅)/i.test(text)) return "line-good";
  if (/(结论|summary|下一步|next step|command|命令|path|路径|status|阶段|approval|审批)/i.test(text)) return "line-key";
  return "";
}

function tryFormatJson(content: string) {
  const text = content.trim();
  if (!text || (!text.startsWith("{") && !text.startsWith("["))) return null;
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return null;
  }
}

function normalizeCode(children: ReactNode): string {
  if (Array.isArray(children)) {
    return children.map((item) => String(item)).join("");
  }
  return String(children ?? "");
}

function extractLang(codeClass?: string) {
  if (!codeClass) return "";
  const match = codeClass.match(/language-([a-zA-Z0-9_-]+)/);
  return match?.[1]?.toLowerCase() || "";
}

function jsonToHtml(input: string) {
  const escaped = input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return escaped.replace(
    /("(?:\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\btrue\b|\bfalse\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)/g,
    (token) => {
      if (token.startsWith('"') && token.endsWith(":")) return `<span class="syntax-key">${token}</span>`;
      if (token.startsWith('"')) return `<span class="syntax-string">${token}</span>`;
      if (token === "true" || token === "false") return `<span class="syntax-boolean">${token}</span>`;
      if (token === "null") return `<span class="syntax-null">${token}</span>`;
      return `<span class="syntax-number">${token}</span>`;
    },
  );
}

function CodeBlock({ codeClass, children }: { codeClass?: string; children: ReactNode }) {
  const [copied, setCopied] = useState(false);
  const raw = normalizeCode(children);
  const lang = extractLang(codeClass);
  const formattedJson = useMemo(() => (lang === "json" ? tryFormatJson(raw) || raw : raw), [lang, raw]);
  const html = useMemo(() => (lang === "json" ? jsonToHtml(formattedJson) : ""), [formattedJson, lang]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(formattedJson);
      setCopied(true);
      toast.success("代码已复制");
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      toast.error("复制代码失败");
    }
  };

  return (
    <div className="code-block-wrap">
      <div className="code-block-head">
        <span className="code-block-lang">{lang || "代码"}</span>
        <button type="button" className="code-copy-btn" onClick={copy}>
          {copied ? "已复制" : "复制"}
        </button>
      </div>
      <pre className={`result-text code-block ${lang ? `language-${lang}` : ""}`}>
        {lang === "json" ? (
          <code className={codeClass} dangerouslySetInnerHTML={{ __html: html }} />
        ) : (
          <code className={codeClass}>{formattedJson}</code>
        )}
      </pre>
    </div>
  );
}

export function MarkdownContent({ content, className = "" }: MarkdownContentProps) {
  const jsonFormatted = tryFormatJson(content);
  if (jsonFormatted) {
    return <pre className={`result-text result-json ${className}`}>{jsonFormatted}</pre>;
  }

  // If content looks like plain text (no markdown indicators), render as pre
  const hasMarkdown = /[#*`\-\[\]|>]/.test(content);
  if (!hasMarkdown) {
    const blocks = content
      .split(/\n{2,}/)
      .map((b) => b.trim())
      .filter(Boolean);
    return (
      <div className={`structured-text ${className}`}>
        {blocks.length ? (
          blocks.map((block, idx) => (
            <div className="text-block" key={`${idx}_${block.slice(0, 18)}`}>
              {block.split("\n").map((line, lineIdx) => (
                <div key={`${idx}_${lineIdx}`} className={`text-line ${classifyLine(line)}`.trim()}>
                  {line}
                </div>
              ))}
            </div>
          ))
        ) : (
          <pre className="result-text">{content}</pre>
        )}
      </div>
    );
  }

  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        components={{
          pre: ({ children }) => <>{children}</>,
          code: ({ children, className: codeClass }) => {
            const raw = normalizeCode(children);
            const isBlock = Boolean(codeClass) || raw.includes("\n");
            if (!isBlock) return <code className="inline-code">{children}</code>;
            return <CodeBlock codeClass={codeClass} children={children} />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
