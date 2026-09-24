import { useRef, useState } from 'react';
import { api } from '../services/api';
import type { ChatTurn } from '../types';

interface Props {
  onInspectWorkItem: (workItemId: number) => void;
}

const SUGGESTIONS = [
  'How much time did we spend on Authentication this sprint?',
  'Which tickets took the most time?',
  'Compare Sprint 24 with Sprint 23',
];

export function ChatPanel({ onInspectWorkItem }: Props) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const conversationId = useRef<string | null>(null);

  async function ask(question: string) {
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    setTurns((t) => [...t, { role: 'user', text: trimmed }]);
    setInput('');
    setLoading(true);

    try {
      const response = await api.chat(trimmed, conversationId.current);
      conversationId.current = response.conversation_id;
      setTurns((t) => [
        ...t,
        {
          role: 'agent',
          text: response.answer,
          evidence: response.evidence,
          flavour: response.unsupported
            ? 'unsupported'
            : response.needs_clarification
              ? 'clarification'
              : 'normal',
        },
      ]);
    } catch (error) {
      setTurns((t) => [
        ...t,
        { role: 'agent', text: (error as Error).message, flavour: 'error' },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel chat">
      <h2>Ask Product Intelligence</h2>

      <div className="chat-log">
        {turns.length === 0 && (
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="chip" onClick={() => ask(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        {turns.map((turn, index) => (
          <div key={index} className={`turn ${turn.role} ${turn.flavour ?? ''}`}>
            <p>{turn.text}</p>

            {turn.evidence && turn.evidence.work_items.length > 0 && (
              <details>
                <summary>
                  Based on {turn.evidence.work_items.length} work item
                  {turn.evidence.work_items.length === 1 ? '' : 's'}
                </summary>
                <ul className="evidence">
                  {turn.evidence.work_items.map((item) => (
                    <li key={item.work_item_id}>
                      <button type="button" className="link" onClick={() => onInspectWorkItem(item.work_item_id)}>
                        #{item.work_item_id}
                      </button>{' '}
                      {item.title ?? ''}
                    </li>
                  ))}
                </ul>
                {Object.keys(turn.evidence.filters_applied).length > 0 && (
                  <p className="note">
                    Filters applied:{' '}
                    {Object.entries(turn.evidence.filters_applied)
                      .map(([k, v]) => `${k.replace(/_/g, ' ')} = ${v}`)
                      .join(', ')}
                  </p>
                )}
              </details>
            )}
          </div>
        ))}

        {loading && <p className="muted">Checking the data…</p>}
      </div>

      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="How much time did we spend on QA this sprint?"
          aria-label="Ask a question about the time-logging data"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>Ask</button>
      </form>

      {turns.length > 0 && (
        <button
          type="button"
          className="link"
          onClick={() => {
            setTurns([]);
            conversationId.current = null;
          }}
        >
          Start a new conversation
        </button>
      )}
    </section>
  );
}
