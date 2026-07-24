"use client";

import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError, apiFetchFormData, reingestResponseSchema } from "@/lib/api";
import { t } from "@/lib/strings";

type State =
  | { step: "idle" }
  | { step: "uploading" }
  | {
      step: "success";
      itemCount: number;
      ingestedAt: string;
      filename: string;
      isNoop: boolean;
    }
  | { step: "error"; message: string };

export function InventoryUploadForm() {
  const [state, setState] = useState<State>({ step: "idle" });
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleUpload(file: File): Promise<void> {
    setState({ step: "uploading" });
    try {
      const formData = new FormData();
      formData.append("file", file);
      const result = await apiFetchFormData(
        "/api/excel/reingest",
        reingestResponseSchema,
        formData,
      );
      setState({
        step: "success",
        itemCount: result.data.itemCount,
        ingestedAt: result.data.ingestedAt,
        filename: file.name,
        isNoop: result.data.isNoop,
      });
    } catch (err) {
      // Validation errors name the specific row/column problem (e.g. "Row 4:
      // Stock must be a whole number") — shown verbatim, not replaced with a
      // canned string, per dashboard_spec.md's inventory screen states.
      const message =
        err instanceof ApiError ? err.message : t("inventory.genericError");
      setState({ step: "error", message });
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  if (state.step === "success") {
    return (
      <div className="space-y-4 rounded-md border p-4">
        <p className="text-sm font-medium">
          {t("inventory.successTitle", { n: String(state.itemCount) })}
        </p>
        <p className="text-sm text-muted-foreground">
          {t("inventory.successSubtitle", {
            filename: state.filename,
            timestamp: new Date(state.ingestedAt).toLocaleString(),
          })}
        </p>
        {state.isNoop ? (
          <p className="text-sm text-muted-foreground">
            {t("inventory.noopNotice")}
          </p>
        ) : null}
        <Button
          variant="outline"
          onClick={() => setState({ step: "idle" })}
        >
          {t("inventory.uploadAnother")}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-md border p-4">
      {state.step === "idle" ? (
        <p className="text-sm text-muted-foreground">{t("inventory.empty")}</p>
      ) : null}
      {state.step === "error" ? (
        <p className="text-sm text-destructive">{state.message}</p>
      ) : null}
      <div className="space-y-1.5">
        <label htmlFor="stock-file" className="text-sm font-medium">
          {t("inventory.selectFile")}
        </label>
        <input
          id="stock-file"
          ref={fileInputRef}
          type="file"
          accept=".xlsx"
          disabled={state.step === "uploading"}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleUpload(file);
          }}
          className="block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-secondary file:px-2.5 file:py-1.5 file:text-sm file:font-medium"
        />
      </div>
      {state.step === "uploading" ? (
        <p className="text-sm text-muted-foreground">
          {t("inventory.uploading")}
        </p>
      ) : null}
    </div>
  );
}
