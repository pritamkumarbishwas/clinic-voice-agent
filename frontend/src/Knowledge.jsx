import {
  BookOpen,
  FileUp,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  TriangleAlert,
  X,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { getApiErrorMessage } from "@/lib/api-error";
import { titleCase } from "@/lib/format";
import {
  useCreateKnowledgeMutation,
  useDeleteKnowledgeMutation,
  useListKnowledgeQuery,
  useSearchKnowledgeMutation,
  useUpdateKnowledgeMutation,
  useUploadKnowledgeMutation,
} from "@/store/api";

const CATEGORIES = [
  "general",
  "services",
  "policies",
  "directions",
  "preparation",
  "doctors",
  "other",
];

const TEXTAREA_CLASS =
  "w-full rounded-lg border border-input bg-background/70 px-3 py-2 text-sm shadow-xs outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25";

function emptyKnowledge() {
  return {
    knowledge_id: "",
    title: "",
    category: "general",
    content: "",
    active: true,
  };
}

function KnowledgeForm({ initial, available, onCancel, onSaved }) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState("");
  const [createKnowledge, { isLoading: creating }] =
    useCreateKnowledgeMutation();
  const [updateKnowledge, { isLoading: updating }] =
    useUpdateKnowledgeMutation();
  const saving = creating || updating;
  const isEditing = Boolean(initial.knowledge_id);

  function setField(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (!form.title.trim() || !form.content.trim()) {
      setError("Title and content are required.");
      return;
    }

    try {
      if (isEditing) {
        await updateKnowledge({
          knowledgeId: initial.knowledge_id,
          title: form.title,
          category: form.category,
          content: form.content,
          active: form.active,
        }).unwrap();
        toast.success("Knowledge entry updated");
      } else {
        await createKnowledge({
          title: form.title,
          category: form.category,
          content: form.content,
          active: form.active,
        }).unwrap();
        toast.success("Knowledge entry added");
      }
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save knowledge entry"));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {isEditing ? "Edit knowledge entry" : "New knowledge entry"}
        </CardTitle>
        <CardDescription>
          Use this for longer clinic FAQs that are not part of the structured
          clinic profile.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <TriangleAlert />
              <AlertTitle>Could not save</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="grid gap-4 sm:grid-cols-[1.5fr_0.7fr]">
            <div className="space-y-1.5">
              <Label htmlFor="knowledge-title">Title</Label>
              <Input
                id="knowledge-title"
                value={form.title}
                onChange={(event) => setField("title", event.target.value)}
                maxLength={200}
                placeholder="Parking and accessibility"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="knowledge-category">Category</Label>
              <Select
                value={form.category}
                onValueChange={(value) => setField("category", value)}
              >
                <SelectTrigger id="knowledge-category" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((category) => (
                    <SelectItem key={category} value={category}>
                      {titleCase(category)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="knowledge-content">Content</Label>
            <textarea
              id="knowledge-content"
              value={form.content}
              onChange={(event) => setField("content", event.target.value)}
              maxLength={50000}
              rows={8}
              className={TEXTAREA_CLASS}
              placeholder="Write the clinic FAQ answer in plain language."
              required
            />
          </div>

          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={form.active}
              onChange={(event) => setField("active", event.target.checked)}
              className="size-4 rounded border-input accent-primary"
            />
            Active in search
          </label>

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="ghost"
              onClick={onCancel}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={saving || !available}
              title={
                available
                  ? undefined
                  : "Set OPENAI_API_KEY and RAG_ENABLED=true to save knowledge"
              }
            >
              {saving && <Loader2 className="animate-spin" />}
              {saving
                ? "Saving..."
                : isEditing
                  ? "Save entry"
                  : "Add entry"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function UploadCard({ available }) {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("general");
  const [active, setActive] = useState(true);
  const [uploadKnowledge, { isLoading }] = useUploadKnowledgeMutation();

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file) {
      toast.error("Choose a PDF, TXT, or Markdown file first");
      return;
    }

    try {
      await uploadKnowledge({
        file,
        title,
        category,
        active,
      }).unwrap();
      setFile(null);
      setTitle("");
      setCategory("general");
      setActive(true);
      event.target.reset();
      toast.success("File uploaded and indexed");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Could not upload the file"));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileUp className="size-4" />
          Upload clinic documents
        </CardTitle>
        <CardDescription>
          PDF, TXT, or Markdown files are split into searchable chunks. Files
          up to 5 MB and PDFs up to 50 pages are supported.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="knowledge-file">File</Label>
            <Input
              id="knowledge-file"
              type="file"
              accept=".pdf,.txt,.md,.markdown"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              disabled={!available || isLoading}
              required
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-[1.5fr_0.7fr]">
            <div className="space-y-1.5">
              <Label htmlFor="upload-title">Title (optional)</Label>
              <Input
                id="upload-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                maxLength={200}
                placeholder="Uses the filename if left blank"
                disabled={!available || isLoading}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="upload-category">Category</Label>
              <Select
                value={category}
                onValueChange={setCategory}
                disabled={!available || isLoading}
              >
                <SelectTrigger id="upload-category" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((item) => (
                    <SelectItem key={item} value={item}>
                      {titleCase(item)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={active}
              onChange={(event) => setActive(event.target.checked)}
              className="size-4 rounded border-input accent-primary"
              disabled={!available || isLoading}
            />
            Active in search
          </label>

          <Button
            type="submit"
            disabled={!available || isLoading}
            title={
              available
                ? undefined
                : "Set OPENAI_API_KEY and RAG_ENABLED=true to upload"
            }
          >
            {isLoading ? <Loader2 className="animate-spin" /> : <FileUp />}
            {isLoading ? "Uploading..." : "Upload and index"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function SearchCard({ available }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searchKnowledge, { isLoading }] = useSearchKnowledgeMutation();

  async function handleSubmit(event) {
    event.preventDefault();
    if (!query.trim()) return;

    try {
      const response = await searchKnowledge({
        query,
        topK: 3,
      }).unwrap();
      setResults(response.results ?? []);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Knowledge search failed"));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Search className="size-4" />
          Test knowledge search
        </CardTitle>
        <CardDescription>
          See what the receptionist would retrieve for a caller question.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Do you have parking?"
            disabled={!available || isLoading}
          />
          <Button
            type="submit"
            disabled={!available || isLoading || !query.trim()}
          >
            {isLoading ? <Loader2 className="animate-spin" /> : <Search />}
            {isLoading ? "Searching..." : "Search"}
          </Button>
        </form>

        {results !== null &&
          (results.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No matching knowledge above the score threshold. The
              receptionist would ask staff to confirm.
            </p>
          ) : (
            <div className="space-y-2">
              {results.map((result, index) => (
                <div
                  key={`${result.title}-${index}`}
                  className="rounded-xl border border-border/70 bg-muted/20 p-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold">
                      {result.title}
                    </span>
                    <Badge variant="outline">
                      {result.source === "doctor" ? "Doctor bio" : "Knowledge"}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      score {result.score}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    {result.text}
                  </p>
                </div>
              ))}
            </div>
          ))}
      </CardContent>
    </Card>
  );
}

export default function Knowledge() {
  const [tab, setTab] = useState("entries");
  const [formState, setFormState] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const knowledgeQuery = useListKnowledgeQuery();
  const { currentData, isError, isFetching, isLoading, refetch } =
    knowledgeQuery;
  const [updateKnowledge] = useUpdateKnowledgeMutation();
  const [deleteKnowledge, { isLoading: deleting }] =
    useDeleteKnowledgeMutation();

  const documents = currentData?.items ?? [];
  const available = Boolean(currentData?.available);
  const enabled = Boolean(currentData?.enabled);
  const loadError = isError
    ? getApiErrorMessage(knowledgeQuery.error, "Could not load knowledge")
    : "";

  function startNew() {
    setFormState(emptyKnowledge());
    setTab("entries");
  }

  function startEdit(document) {
    setFormState({
      knowledge_id: document.knowledge_id,
      title: document.title,
      category: document.category,
      content: document.content,
      active: document.active,
    });
    setTab("entries");
  }

  async function toggleActive(document) {
    try {
      await updateKnowledge({
        knowledgeId: document.knowledge_id,
        active: !document.active,
      }).unwrap();
      toast.success(document.active ? "Entry deactivated" : "Entry activated");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Could not update knowledge entry"));
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    try {
      await deleteKnowledge(pendingDelete.knowledge_id).unwrap();
      toast.success("Knowledge entry deleted");
      setPendingDelete(null);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Could not delete knowledge entry"));
    }
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <PageHeader
        icon={BookOpen}
        eyebrow="Knowledge"
        title="Clinic knowledge base"
        description="Manage longer FAQs the receptionist can search during calls. Structured clinic and doctor details always take priority."
        actions={
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={isFetching ? "animate-spin" : ""} />
              Refresh
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={startNew}
              disabled={!available}
            >
              <Plus />
              New entry
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        {available ? (
          <Badge variant="success">RAG ready</Badge>
        ) : (
          <Badge variant="warning">
            {enabled ? "OpenAI key required" : "RAG disabled"}
          </Badge>
        )}
        {currentData?.embedding_model && (
          <span>{currentData.embedding_model}</span>
        )}
        <span>
          {documents.length} entr{documents.length === 1 ? "y" : "ies"}
        </span>
      </div>

      {!available && currentData && (
        <Alert>
          <TriangleAlert />
          <AlertTitle>Knowledge search is not available</AlertTitle>
          <AlertDescription>
            Set <code>OPENAI_API_KEY</code> and{" "}
            <code>RAG_ENABLED=true</code> on the backend to add, upload, or
            search knowledge. Booking and structured clinic answers still work.
          </AlertDescription>
        </Alert>
      )}

      {loadError && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Could not load knowledge</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-2">
            <span>{loadError}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={isFetching ? "animate-spin" : ""} />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="grid w-full grid-cols-3 sm:inline-flex sm:w-fit">
          <TabsTrigger value="entries">
            <BookOpen />
            Entries
            <span className="rounded-full bg-background/70 px-1.5 text-[10px] tabular-nums">
              {documents.length}
            </span>
          </TabsTrigger>
          <TabsTrigger value="upload">
            <FileUp />
            Upload
          </TabsTrigger>
          <TabsTrigger value="search">
            <Search />
            Test search
          </TabsTrigger>
        </TabsList>

        <TabsContent value="entries" className="space-y-5">
          {formState && (
            <KnowledgeForm
              key={formState.knowledge_id || "new"}
              initial={formState}
              available={available}
              onCancel={() => setFormState(null)}
              onSaved={() => setFormState(null)}
            />
          )}

          {pendingDelete && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Delete "{pendingDelete.title}"?</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>This removes the entry and its search index permanently.</p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={confirmDelete}
                disabled={deleting}
              >
                {deleting && <Loader2 className="animate-spin" />}
                Delete entry
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setPendingDelete(null)}
                disabled={deleting}
              >
                <X />
                Keep entry
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Knowledge entries</CardTitle>
          <CardDescription>
            Inactive entries are kept but excluded from receptionist search.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <Skeleton key={index} className="h-24 rounded-xl" />
              ))}
            </div>
          ) : documents.length === 0 ? (
            <EmptyState
              icon={BookOpen}
              title="No knowledge entries yet"
              description="Add an FAQ or upload a document to help the receptionist answer extra clinic questions."
              compact
              action={
                <Button
                  type="button"
                  size="sm"
                  onClick={startNew}
                  disabled={!available}
                >
                  <Plus />
                  New entry
                </Button>
              }
            />
          ) : (
            <div className="space-y-3">
              {documents.map((document) => (
                <div
                  key={document.knowledge_id}
                  className="rounded-xl border border-border/70 p-4"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold">
                          {document.title}
                        </h3>
                        <Badge variant="outline">
                          {titleCase(document.category)}
                        </Badge>
                        <Badge
                          variant={document.active ? "success" : "secondary"}
                        >
                          {document.active ? "Active" : "Inactive"}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {document.chunk_count} chunk
                          {document.chunk_count === 1 ? "" : "s"}
                        </span>
                      </div>
                      <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                        {document.content}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleActive(document)}
                        disabled={!available}
                      >
                        {document.active ? "Deactivate" : "Activate"}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => startEdit(document)}
                        aria-label="Edit knowledge entry"
                        title="Edit"
                      >
                        <Pencil />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => setPendingDelete(document)}
                        aria-label="Delete knowledge entry"
                        title="Delete"
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="upload">
          <UploadCard available={available} />
        </TabsContent>

        <TabsContent value="search">
          <SearchCard available={available} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
