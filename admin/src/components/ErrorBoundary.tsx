import { Component, type ErrorInfo, type ReactNode } from "react";
import { clientLog } from "../lib/logger";

export class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    clientLog("client.error.boundary", "error", {
      message: error.message,
      component_stack: info.componentStack?.slice(0, 500),
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen items-center justify-center bg-zinc-950 text-zinc-300">
          Something went wrong. Please reload.
        </div>
      );
    }
    return this.props.children;
  }
}
