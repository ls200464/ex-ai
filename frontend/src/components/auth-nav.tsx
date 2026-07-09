"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function AuthNav() {
  const { user, isAuthenticated, isLoading, logout } = useAuth();

  return (
    <nav className="flex items-center gap-4 text-sm text-muted-foreground">
      <Link href="/" className="hover:text-foreground transition-colors">
        Personas
      </Link>

      {isLoading ? (
        <span className="text-xs text-muted-foreground">加载中...</span>
      ) : isAuthenticated && user ? (
        <>
          <Link
            href="/upload"
            className={cn(buttonVariants({ size: "sm" }), "text-xs")}
          >
            + 新建 Persona
          </Link>
          <span className="text-xs hidden sm:inline">{user.display_name || user.email}</span>
          <button
            onClick={logout}
            className="text-xs hover:text-foreground transition-colors"
          >
            退出
          </button>
        </>
      ) : (
        <>
          <Link href="/login" className="hover:text-foreground transition-colors">
            登录
          </Link>
          <Link
            href="/register"
            className={cn(buttonVariants({ size: "sm" }), "text-xs")}
          >
            注册
          </Link>
        </>
      )}
    </nav>
  );
}
