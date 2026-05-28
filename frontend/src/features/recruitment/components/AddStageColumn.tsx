import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Check, Plus } from "lucide-react";

export function AddStageColumn({ onAdd }: { onAdd: (name: string) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = () => {
    const v = name.trim();
    if (!v) return;
    onAdd(v);
    setName("");
    setOpen(false);
  };

  return (
    <div className="flex w-10 shrink-0 flex-col self-stretch sm:w-12">
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) setTimeout(() => inputRef.current?.focus(), 0);
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          className="flex h-full min-h-[120px] w-full min-w-0 max-w-full flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 px-1 hover:border-primary/50 hover:bg-primary/5 transition-colors cursor-pointer"
          title="Ajouter une étape"
        >
          <Plus className="h-5 w-5 shrink-0 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-3">
        <p className="text-sm font-medium mb-2">Nouvelle étape</p>
        <div className="flex gap-2">
          <Input
            ref={inputRef}
            placeholder="Ex: Test technique"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
            className="flex-1 h-8 text-sm"
          />
          <Button size="sm" className="h-8 px-3" disabled={!name.trim()} onClick={submit}>
            <Check className="h-4 w-4" />
          </Button>
        </div>
      </PopoverContent>
    </Popover>
    </div>
  );
}
