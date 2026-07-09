"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { personaApi, memoryApi, extractionApi, uploadApi, type PersonaDetail, type MemoryResponse, type ExtractionStatusResponse, type UploadResponse } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Label } from "@/components/ui/label";

const LAYER_LABELS: Record<string, string> = {
  hard_rules: "硬规则",
  identity: "身份特征",
  speaking_style: "说话风格",
  emotional_patterns: "情感模式",
  relational_behavior: "关系行为",
};

const CATEGORY_LABELS: Record<string, string> = {
  shared_experience: "共同经历",
  conflict: "冲突",
  inside_joke: "内部梗",
  habit_pattern: "习惯模式",
  milestone: "重要节点",
  preference: "偏好",
  other: "其他",
};

function JsonDisplay({ data }: { data: any }) {
  if (
    !data ||
    (Array.isArray(data) && data.length === 0) ||
    (typeof data === "object" && Object.keys(data).length === 0)
  ) {
    return <p className="text-sm text-muted-foreground italic">暂无数据</p>;
  }
  return (
    <pre className="text-xs bg-muted/50 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap max-h-80">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

export default function PersonaDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useRequireAuth();
  const [persona, setPersona] = useState<PersonaDetail | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  if (authLoading || !isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-4">
        <div className="h-8 w-48 bg-muted rounded animate-pulse" />
        <div className="h-4 w-96 bg-muted rounded animate-pulse" />
      </div>
    );
  }
  const [memories, setMemories] = useState<MemoryResponse[]>([]);
  const [uploads, setUploads] = useState<UploadResponse[]>([]);
  const [extractionStatus, setExtractionStatus] = useState<ExtractionStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [memoriesLoading, setMemoriesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("hard_rules");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadType, setUploadType] = useState("wechat");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [memoriesPage, setMemoriesPage] = useState(1);
  const [memoriesTotal, setMemoriesTotal] = useState(0);
  const [loadingMoreMemories, setLoadingMoreMemories] = useState(false);

  const loadPersona = useCallback(() => {
    personaApi
      .get(params.id)
      .then(setPersona)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [params.id]);

  const loadMemories = useCallback((page = 1, append = false) => {
    setMemoriesLoading(true);
    memoryApi
      .list(params.id, undefined, page, 50)
      .then((res) => {
        setMemoriesTotal(res.total);
        if (append) {
          setMemories((prev) => [...prev, ...res.items]);
        } else {
          setMemories(res.items);
        }
        setMemoriesPage(page);
      })
      .catch(() => {})
      .finally(() => setMemoriesLoading(false));
  }, [params.id]);

  const loadMoreMemories = () => {
    if (loadingMoreMemories) return;
    setLoadingMoreMemories(true);
    const nextPage = memoriesPage + 1;
    memoryApi
      .list(params.id, undefined, nextPage, 50)
      .then((res) => {
        setMemories((prev) => [...prev, ...res.items]);
        setMemoriesPage(nextPage);
      })
      .catch(() => {})
      .finally(() => setLoadingMoreMemories(false));
  };

  const loadUploads = useCallback(() => {
    uploadApi
      .list(params.id)
      .then(setUploads)
      .catch(() => {});
  }, [params.id]);

  const pollExtractionStatus = useCallback(() => {
    extractionApi
      .status(params.id)
      .then((status) => {
        setExtractionStatus(status);
        if (status.status === "completed") {
          // Reload persona data
          loadPersona();
          loadMemories();
        }
      })
      .catch(() => {});
  }, [params.id, loadPersona, loadMemories]);

  useEffect(() => {
    loadPersona();
    loadMemories();
    loadUploads();
  }, [loadPersona, loadMemories, loadUploads]);

  // Poll extraction status if persona is not ready OR extraction was manually triggered
  useEffect(() => {
    const shouldPoll =
      (persona && persona.status !== "ready" && persona.status !== "archived") ||
      (extractionStatus && (extractionStatus.status === "processing" || extractionStatus.status === "starting"));

    if (shouldPoll) {
      pollExtractionStatus();
      const interval = setInterval(pollExtractionStatus, 3000);
      return () => clearInterval(interval);
    }
  }, [persona?.status, extractionStatus?.status, pollExtractionStatus]);

  const handleDelete = async () => {
    if (!confirm("确定要删除这个 Persona 吗？此操作不可撤销。")) return;
    try {
      await personaApi.delete(params.id);
      router.push("/");
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleExtract = async () => {
    try {
      setExtractionStatus({ task_id: params.id, status: "processing", progress_pct: 0, stage: "starting", error: null });
      await extractionApi.extractAll(params.id);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleClearAndReExtract = async () => {
    if (!confirm("确定要清除所有记忆并重新提取吗？此操作不可撤销。")) return;
    try {
      // Delete all existing memories
      await memoryApi.deleteAll(params.id);
      // Reset memory state
      setMemories([]);
      setMemoriesPage(1);
      setMemoriesTotal(0);
      // Trigger fresh extraction
      setExtractionStatus({ task_id: params.id, status: "processing", progress_pct: 0, stage: "starting", error: null });
      await extractionApi.extractAll(params.id);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleUploadToExisting = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setUploadMsg("上传中...");
    try {
      const upload = await uploadApi.upload(params.id, uploadFile, uploadType);
      setUploadMsg("解析中...");

      // Wait for parse to finish
      await new Promise<void>((resolve) => {
        const interval = setInterval(async () => {
          try {
            const status = await uploadApi.status(upload.upload_id);
            setUploadMsg(`解析中: ${Math.round(status.progress_pct * 100)}%`);
            if (status.status === "done") { clearInterval(interval); resolve(); }
            if (status.status === "error") { clearInterval(interval); setError(status.error_message || "解析失败"); resolve(); }
          } catch { clearInterval(interval); resolve(); }
        }, 1500);
      });

      setUploadMsg("上传完成，开始提取...");
      setUploadFile(null);
      setUploadOpen(false);
      setUploading(false);
      setUploadMsg("");

      // Refresh uploads list
      loadUploads();
      // Trigger extraction automatically
      await handleExtract();
    } catch (err: any) {
      setError(err.message);
      setUploading(false);
      setUploadMsg("");
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-96" />
        <Skeleton className="h-8 w-full mt-6" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
        <Button variant="outline" className="mt-4" onClick={() => router.push("/")}>
          返回首页
        </Button>
      </div>
    );
  }

  if (!persona) return null;

  const layers = [
    { key: "hard_rules", data: persona.hard_rules },
    { key: "identity", data: persona.identity },
    { key: "speaking_style", data: persona.speaking_style },
    { key: "emotional_patterns", data: persona.emotional_patterns },
    { key: "relational_behavior", data: persona.relational_behavior },
  ];

  const isExtracting = !!extractionStatus &&
    (extractionStatus.status === "processing" || extractionStatus.status === "starting");

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold">{persona.display_name || persona.name}</h1>
            <Badge variant={persona.status === "ready" ? "default" : "secondary"}>
              {persona.status === "ready" ? "就绪" : persona.status === "archived" ? "已归档" : "生成中"}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">@{persona.name}</p>
        </div>
        <div className="flex gap-2">
          {persona.status === "ready" && (
            <Link
              href={`/personas/${persona.id}/chat`}
              className={cn(buttonVariants(), "")}
            >
              💬 开始对话
            </Link>
          )}
          <Button variant="outline" onClick={handleExtract} disabled={isExtracting}>
            {isExtracting ? "⏳ 提取中..." : "🔄 触发提取"}
          </Button>
          <Button variant="outline" onClick={handleClearAndReExtract} disabled={isExtracting}>
            🗑️ 清除并重新提取
          </Button>
          <Button variant="destructive" size="sm" onClick={handleDelete}>
            删除
          </Button>
        </div>
      </div>

      {/* Extraction progress */}
      {isExtracting && (
        <Card className="mb-6 border-primary/30">
          <CardContent className="py-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium">AI 提取进行中...</p>
              <p className="text-xs text-muted-foreground">{extractionStatus.stage || "处理中"}</p>
            </div>
            <Progress value={extractionStatus.progress_pct * 100} />
          </CardContent>
        </Card>
      )}

      {extractionStatus?.status === "failed" && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive mb-6">
          提取失败: {extractionStatus.error || "未知错误"}
          <button className="ml-2 underline" onClick={handleExtract}>重试</button>
        </div>
      )}

      {/* Tags */}
      {persona.tags && persona.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-6">
          {persona.tags.map((tag: any, i: number) => (
            <Badge key={i} variant="secondary">
              {typeof tag === "string" ? tag : tag.name || tag.category || tag}
            </Badge>
          ))}
        </div>
      )}

      <Tabs defaultValue="hard_rules" value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4 flex-wrap h-auto gap-1">
          {layers.map((l) => (
            <TabsTrigger key={l.key} value={l.key}>
              {LAYER_LABELS[l.key] || l.key}
            </TabsTrigger>
          ))}
          <TabsTrigger value="memories">💾 记忆 ({memories.length})</TabsTrigger>
          <TabsTrigger value="sources">📁 源文件 ({uploads.length})</TabsTrigger>
        </TabsList>

        {/* Layer tabs */}
        {layers.map((l) => (
          <TabsContent key={l.key} value={l.key}>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{LAYER_LABELS[l.key] || l.key}</CardTitle>
              </CardHeader>
              <CardContent>
                <JsonDisplay data={l.data} />
              </CardContent>
            </Card>
          </TabsContent>
        ))}

        {/* Memories tab */}
        <TabsContent value="memories">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">提取的记忆</CardTitle>
            </CardHeader>
            <CardContent>
              {memoriesLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-20 w-full" />
                  ))}
                </div>
              ) : memories.length === 0 ? (
                <p className="text-sm text-muted-foreground italic py-8 text-center">
                  暂无记忆。上传聊天记录并触发 AI 提取后，这里会显示提取出的记忆。
                </p>
              ) : (
                <div className="space-y-3">
                  {memories.map((mem) => (
                    <div
                      key={mem.id}
                      className="rounded-lg border p-3 hover:bg-muted/50 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <p className="font-medium text-sm">{mem.title || "无标题"}</p>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            {CATEGORY_LABELS[mem.category] || mem.category}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {mem.importance}/10
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground line-clamp-2">{mem.content}</p>
                      {mem.emotional_tone && (
                        <p className="text-xs text-muted-foreground mt-1">
                          情绪: {mem.emotional_tone}
                        </p>
                      )}
                    </div>
                  ))}
                  {memories.length < memoriesTotal && (
                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={loadMoreMemories}
                      disabled={loadingMoreMemories}
                    >
                      {loadingMoreMemories ? "加载中..." : `加载更多 (${memories.length}/${memoriesTotal})`}
                    </Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sources tab */}
        <TabsContent value="sources">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">上传的源文件</CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setUploadOpen(!uploadOpen)}
                >
                  {uploadOpen ? "取消" : "📁 上传更多记录"}
                </Button>
              </div>
              {uploadOpen && (
                <div className="mt-3 p-4 border rounded-lg bg-muted/30 space-y-3">
                  <div>
                    <Label className="text-sm font-medium mb-1 block">来源类型</Label>
                    <div className="flex gap-2">
                      {[
                        { key: "wechat", label: "微信" },
                        { key: "qq", label: "QQ" },
                      ].map((t) => (
                        <Button
                          key={t.key}
                          variant={uploadType === t.key ? "default" : "outline"}
                          size="sm"
                          onClick={() => setUploadType(t.key)}
                          disabled={uploading}
                        >
                          {t.label}
                        </Button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <input
                      type="file"
                      accept=".txt"
                      className="text-sm"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) setUploadFile(f);
                      }}
                      disabled={uploading}
                    />
                  </div>
                  {uploadFile && (
                    <p className="text-xs text-muted-foreground">
                      {uploadFile.name} ({(uploadFile.size / 1024).toFixed(1)} KB)
                    </p>
                  )}
                  {uploadMsg && (
                    <p className="text-sm text-primary font-medium">{uploadMsg}</p>
                  )}
                  <Button
                    size="sm"
                    onClick={handleUploadToExisting}
                    disabled={!uploadFile || uploading}
                  >
                    {uploading ? "⏳ 处理中..." : "开始上传并提取"}
                  </Button>
                </div>
              )}
            </CardHeader>
            <CardContent>
              {uploads.length === 0 ? (
                <p className="text-sm text-muted-foreground italic py-8 text-center">
                  暂无上传文件
                </p>
              ) : (
                <div className="space-y-2">
                  {uploads.map((u) => (
                    <div
                      key={u.upload_id}
                      className="flex items-center justify-between text-sm bg-muted/50 rounded-lg px-3 py-2"
                    >
                      <div>
                        <p className="font-medium">{u.filename}</p>
                        <p className="text-xs text-muted-foreground">
                          {u.file_type.toUpperCase()} · {u.file_size ? `${(u.file_size / 1024).toFixed(1)} KB` : "未知大小"}
                        </p>
                      </div>
                      <Badge variant={u.status === "done" ? "default" : "secondary"}>
                        {u.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
