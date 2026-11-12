import { useState } from "react";
import { toast } from "sonner";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";

const inputCls = "border-purple-500/20 bg-black/40";
const EMPTY = { question: "", answer: "" };

const act = async (fn, msg, after) => {
  try {
    await fn();
    toast.success(msg);
    after?.();
  } catch (e) {
    toast.error(formatApiError(e));
  }
};

const AnswerForm = ({ editing, onDone }) => {
  const [f, setF] = useState(editing || EMPTY);
  const submit = (e) => {
    e.preventDefault();
    const body = { question: f.question, answer: f.answer };
    act(() => (editing ? api.patch(`/admin/assistant/answers/${editing.id}`, body) : api.post("/admin/assistant/answers", body)),
      editing ? "Answer updated" : "Answer saved", () => { setF(EMPTY); onDone(); });
  };
  return (
    <form onSubmit={submit} className="card-lux space-y-3 p-6" data-testid="bot-answer-form">
      <p className="label-eyebrow">{editing ? "Edit answer" : "New answer"}</p>
      <Input data-testid="bot-answer-question-input" required minLength={3} maxLength={200} placeholder="Question, e.g. How long does deposit approval take?" value={f.question} onChange={(e) => setF({ ...f, question: e.target.value })} className={inputCls} />
      <Textarea data-testid="bot-answer-answer-input" required minLength={3} maxLength={1500} rows={5} placeholder="Your exact answer" value={f.answer} onChange={(e) => setF({ ...f, answer: e.target.value })} className={inputCls} />
      <p className="text-xs text-slate-500">Scara will give this answer whenever someone asks something similar, in their own language.</p>
      <div className="flex gap-2">
        {editing && <Button type="button" variant="outline" onClick={() => onDone()} data-testid="bot-answer-cancel-button" className="flex-1 rounded-full border-purple-500/30 bg-transparent">Cancel</Button>}
        <Button data-testid="bot-answer-save-button" className="flex-1 rounded-full bg-purple-600 hover:bg-purple-500"><Plus className="mr-2 h-4 w-4" /> {editing ? "Save changes" : "Save answer"}</Button>
      </div>
    </form>
  );
};

const AnswerRow = ({ a, canEdit, onEdit, reload }) => (
  <div className="card-lux p-5" data-testid={`bot-answer-row-${a.id}`}>
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <p className="font-semibold text-white">{a.question}</p>
        <p className="mt-2 whitespace-pre-line text-sm text-slate-400">{a.answer}</p>
      </div>
      {canEdit && (
        <div className="flex shrink-0 items-center gap-1">
          <Switch checked={a.active} data-testid={`bot-answer-toggle-${a.id}`}
            onCheckedChange={(v) => act(() => api.patch(`/admin/assistant/answers/${a.id}`, { active: v }), v ? "Answer on" : "Answer off", reload)} />
          <Button size="sm" variant="ghost" onClick={() => onEdit(a)} data-testid={`bot-answer-edit-${a.id}`} className="text-slate-400 hover:text-white"><Pencil className="h-4 w-4" /></Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="sm" variant="ghost" data-testid={`bot-answer-delete-${a.id}`} className="text-slate-500 hover:text-red-300"><Trash2 className="h-4 w-4" /></Button>
            </AlertDialogTrigger>
            <AlertDialogContent className="border-purple-500/20 bg-[#0b0816] text-slate-200">
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this answer?</AlertDialogTitle>
                <AlertDialogDescription>Scara will stop using it right away.</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel className="bg-transparent">Cancel</AlertDialogCancel>
                <AlertDialogAction data-testid={`bot-answer-delete-confirm-${a.id}`} className="bg-red-600 hover:bg-red-500"
                  onClick={() => act(() => api.delete(`/admin/assistant/answers/${a.id}`), "Answer deleted", reload)}>Delete</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      )}
    </div>
    {!a.active && <p className="mt-2 text-xs text-amber-300">Off — Scara is not using this answer</p>}
  </div>
);

export default function BotAnswers() {
  const { user } = useAuth();
  const canEdit = user?.role === "admin";
  const { data, reload } = useFetch("/admin/assistant/answers");
  const [editing, setEditing] = useState(null);
  return (
    <>
      <PageHeader eyebrow="AI assistant" title="Bot answers" desc="Save your own answers to common questions so Scara replies exactly your way." />
      <div className={`grid gap-6 ${canEdit ? "lg:grid-cols-[380px_1fr]" : ""}`}>
        {canEdit && <AnswerForm key={editing?.id || "new"} editing={editing} onDone={() => { setEditing(null); reload(); }} />}
        <div className="space-y-3" data-testid="bot-answer-list">
          {data?.length === 0 && <EmptyState text="No saved answers yet." testId="bot-answer-empty" />}
          {data?.map((a) => <AnswerRow key={a.id} a={a} canEdit={canEdit} onEdit={setEditing} reload={reload} />)}
        </div>
      </div>
    </>
  );
}
