"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { personaApi, uploadApi, extractionApi } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { Progress } from "@/components/ui/progress";

type Step = "create" | "upload" | "processing" | "done";

const STAGE_LABELS: Record<string, string> = {
  pending: "等待处理...",
  parsing: "解析聊天记录中...",
  parsed: "解析完成",
  done: "解析完成",
  extracting_persona: "提取人格特征中...",
  extracting_memories: "提取记忆中...",
  loading_messages: "加载消息中...",
  completed: "完成！",
  error: "处理出错",
};

export default function UploadPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useRequireAuth();
  const [step, setStep] = useState<Step>("create");

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  if (authLoading || !isAuthenticated) {
    return (
      <div className="max-w-xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-8">新建 Persona</h1>
        <div className="text-center text-muted-foreground">加载中...</div>
      </div>
    );
  }
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileType, setFileType] = useState("wechat");
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setError(null);
    try {
      const persona = await personaApi.create(name.trim(), displayName.trim() || undefined);
      setPersonaId(persona.id);
      setStep("upload");
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleUpload = async () => {
    if (!file || !personaId) return;
    setError(null);
    setStep("processing");
    setStatusText("上传文件中...");
    setProgress(5);

    try {
      const upload = await uploadApi.upload(personaId, file, fileType);
      setProgress(15);
      setStatusText("解析中...");

      // Phase 1: Poll upload/parse status
      let uploadDone = false;
      const pollUpload = new Promise<void>((resolve) => {
        const interval = setInterval(async () => {
          try {
            const status = await uploadApi.status(upload.upload_id);
            setProgress(10 + status.progress_pct * 40); // 10-50%
            setStatusText(STAGE_LABELS[status.status] || status.stage || "处理中...");

            if (status.status === "done") {
              clearInterval(interval);
              uploadDone = true;
              resolve();
            } else if (status.status === "error") {
              clearInterval(interval);
              setError(status.error_message || "解析出错");
              setStep("upload");
              resolve();
            }
          } catch {
            clearInterval(interval);
            resolve();
          }
        }, 1200);
      });

      await pollUpload;

      if (!uploadDone) return;

      // Phase 2: Poll extraction status
      setProgress(50);
      setStatusText("提取中...");

      const pollExtraction = new Promise<void>((resolve) => {
        const interval = setInterval(async () => {
          try {
            const status = await extractionApi.status(personaId!);
            setProgress(50 + status.progress_pct * 50); // 50-100%
            setStatusText(STAGE_LABELS[status.stage || ""] || status.stage || "提取中...");

            if (status.status === "completed") {
              clearInterval(interval);
              setProgress(100);
              setStatusText("完成！");
              setStep("done");
              resolve();
            } else if (status.status === "failed") {
              clearInterval(interval);
              setError(status.error || "提取失败");
              // Still mark as done since parsing succeeded
              setStep("done");
              resolve();
            }
          } catch {
            // Keep polling
          }
        }, 1500);
      });

      await pollExtraction;
    } catch (err: any) {
      setError(err.message);
      setStep("upload");
    }
  };

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-8">新建 Persona</h1>

      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-8">
        {[
          { key: "create", label: "创建" },
          { key: "upload", label: "上传" },
          { key: "processing", label: "处理" },
          { key: "done", label: "完成" },
        ].map((s, i) => (
          <div key={s.key} className="flex items-center gap-2">
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium ${
                step === s.key
                  ? "bg-primary text-primary-foreground"
                  : ["create", "upload", "processing", "done"].indexOf(step) > i
                  ? "bg-primary/80 text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {i + 1}
            </div>
            <span className="text-xs text-muted-foreground hidden sm:inline">{s.label}</span>
            {i < 3 && <div className="w-8 h-px bg-border" />}
          </div>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive mb-6">
          {error}
        </div>
      )}

      {/* Step 1: Create Persona */}
      {step === "create" && (
        <Card>
          <CardHeader>
            <CardTitle>创建 Persona</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-sm font-medium mb-1.5 block">ID (英文标识)</Label>
              <Input
                placeholder="例如: xiao-mei"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">
                用于 URL 的唯一标识，只能用小写字母和连字符
              </p>
            </div>
            <div>
              <Label className="text-sm font-medium mb-1.5 block">显示名称</Label>
              <Input
                placeholder="例如: 小美"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>
            <Button onClick={handleCreate} disabled={!name.trim()} className="w-full">
              下一步
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Upload */}
      {step === "upload" && (
        <Card>
          <CardHeader>
            <CardTitle>上传聊天记录</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-sm font-medium mb-1.5 block">来源类型</Label>
              <div className="flex gap-2">
                {[
                  { key: "wechat", label: "微信" },
                  { key: "qq", label: "QQ" },
                ].map((t) => (
                  <Button
                    key={t.key}
                    variant={fileType === t.key ? "default" : "outline"}
                    size="sm"
                    onClick={() => setFileType(t.key)}
                  >
                    {t.label}
                  </Button>
                ))}
              </div>
            </div>
            <div>
              <Label className="text-sm font-medium mb-1.5 block">选择文件</Label>
              <div
                className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => document.getElementById("file-input")?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const f = e.dataTransfer.files[0];
                  if (f) setFile(f);
                }}
              >
                {file ? (
                  <div>
                    <p className="font-medium">{file.name}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-muted-foreground">拖拽文件到这里，或点击选择</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      支持 .txt 格式的聊天记录导出文件
                    </p>
                  </div>
                )}
                <input
                  id="file-input"
                  type="file"
                  accept=".txt"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setFile(f);
                  }}
                />
              </div>
            </div>
            <Button onClick={handleUpload} disabled={!file} className="w-full">
              开始解析
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Processing */}
      {step === "processing" && (
        <Card>
          <CardHeader>
            <CardTitle>处理中...</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Progress value={progress} />
            <p className="text-sm text-muted-foreground text-center">{statusText}</p>
            <p className="text-xs text-muted-foreground text-center">
              正在解析聊天记录并提取 AI 人格，可能需要 1-3 分钟...
            </p>
          </CardContent>
        </Card>
      )}

      {/* Step 4: Done */}
      {step === "done" && (
        <Card>
          <CardHeader>
            <CardTitle>✅ 完成！</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              聊天记录已解析，AI 人格特征已提取。现在可以查看详情或开始对话。
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => router.push(`/personas/${personaId}`)}
              >
                查看 Persona
              </Button>
              <Button className="flex-1" onClick={() => router.push(`/personas/${personaId}/chat`)}>
                开始对话
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
