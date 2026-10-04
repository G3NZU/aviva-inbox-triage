const EXAMPLES = [
  "Which is the most relevant thread to focus on?",
  "What is outstanding on PIN-MTR-552301?",
  "Was there any action required for Bridgegate Brokers?",
  "Which threads involve a solicitor?",
];

/**
 * Example questions that fill the box: they never send, as each question is a paid call, so the user presses
 * Ask. They show what Ask is for better than a description would. Props: the handler that fills the box.
 */
export default function AskIntro({ onExample }: { onExample: (question: string) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-ink-2">Try:</span>
      {EXAMPLES.map((example) => (
        <button key={example} type="button" onClick={() => onExample(example)}
          className="rounded-full border border-line-strong bg-surface px-3 py-1 text-sm transition-colors duration-150
            ease-standard hover:border-accent hover:text-accent-strong">
          {example}
        </button>
      ))}
    </div>
  );
}
