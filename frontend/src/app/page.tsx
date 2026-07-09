"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { personaApi, type PersonaSummary } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useRequireAuth } from "@/lib/auth";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

function PersonaCard({ persona }: { persona: PersonaSummary }) {
  const statusMap: Record<string, { label: string; variant: "default" | "secondary" | "outline" }> = {
    creating: { label: "生成中", variant: "secondary" },
    ready: { label: "就绪", variant: "default" },
    archived: { label: "已归档", variant: "outline" },
  };
  const st = statusMap[persona.status] || statusMap.creating;

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{persona.display_name || persona.name}</CardTitle>
          <Badge variant={st.variant}>{st.label}</Badge>
        </div>
        <p className="text-xs text-muted-foreground">@{persona.name}</p>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-1.5">
          {persona.tags?.map((tag: any, i: number) => (
            <Badge key={i} variant="outline" className="text-xs">
              {tag.name || tag.category}
            </Badge>
          ))}
          {(!persona.tags || persona.tags.length === 0) && (
            <span className="text-xs text-muted-foreground">暂无标签</span>
          )}
        </div>
      </CardContent>
      <CardFooter className="flex gap-2">
        <Link
            href={`/personas/${persona.id}`}
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "flex-1")}
          >
            查看详情
          </Link>
        {persona.status === "ready" && (
          <Link
            href={`/personas/${persona.id}/chat`}
            className={cn(buttonVariants({ size: "sm" }), "flex-1")}
          >
            开始对话
          </Link>
        )}
      </CardFooter>
    </Card>
  );
}

function PersonaSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-3 w-20 mt-1" />
      </CardHeader>
      <CardContent>
        <div className="flex gap-1.5">
          <Skeleton className="h-5 w-12 rounded-full" />
          <Skeleton className="h-5 w-16 rounded-full" />
        </div>
      </CardContent>
      <CardFooter className="flex gap-2">
        <Skeleton className="h-9 flex-1" />
        <Skeleton className="h-9 flex-1" />
      </CardFooter>
    </Card>
  );
}

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useRequireAuth();
  const [personas, setPersonas] = useState<PersonaSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Auth guard
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    personaApi
      .list()
      .then((res) => setPersonas(res.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [isAuthenticated]);

  if (authLoading || !isAuthenticated) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (<PersonaSkeleton key={i} />))}
        </div>
      </div>
    );
  }

  const load = () => {
    personaApi
      .list()
      .then((res) => setPersonas(res.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">我的 Personas</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            导入聊天记录，生成用 ta 的方式跟你说话的 AI 人格
          </p>
        </div>
        <Link href="/upload" className={cn(buttonVariants(), "px-4")}>
          + 新建 Persona
        </Link>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive mb-6">
          {error}
          <button className="ml-2 underline" onClick={() => { setError(null); load(); }}>
            重试
          </button>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (<PersonaSkeleton key={i} />))}
        </div>
      ) : personas.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-4xl mb-4">💔</p>
          <h2 className="text-lg font-semibold mb-2">还没有 Persona</h2>
          <p className="text-muted-foreground text-sm mb-6">
            上传微信/QQ聊天记录，创建你的第一个 AI Persona
          </p>
          <Link href="/upload" className={cn(buttonVariants(), "px-4")}>
            开始创建
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {personas.map((p) => (<PersonaCard key={p.id} persona={p} />))}
        </div>
      )}
    </div>
  );
}
